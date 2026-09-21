#!/usr/bin/env python
"""Materialize the V1 Beta R2 web-assets from registry-declared SDF sources.

R2 deliberately reuses the R1 SQLite unchanged.  Exact instance SDFs and
shared canonical chemistry SDFs are kept in different web namespaces.
"""
from __future__ import annotations

import csv, hashlib, json, math, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from rdkit import Chem

APP = Path(__file__).resolve().parents[1]
SCI = Path('/Users/jxs794/Desktop/E3Ligandalyzer')
R1 = APP/'releases/v1.0-locked-20260908-r1'
STAGE = SCI/'Rebuild_Staging/v1.0-lock-20260908-r1'
OUT = APP/'releases/v1.0-beta-r2-20260912'
AUDIT = SCI/'Corpus_Audit'
DB_SHA = '33afb375ade1cbbb428230bfc226fe0b5b8a43a3231bfa699ba5ddc576f89689'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    if sha(src)!=sha(dst): raise RuntimeError(f'hash mismatch: {src}')
    return sha(dst)

def sdf_ok(path):
    mol=Chem.MolFromMolFile(str(path),sanitize=True,removeHs=False)
    if mol is None or not mol.GetNumAtoms(): return None,'RDKit parse/sanitize failed'
    conf=mol.GetConformer() if mol.GetNumConformers() else None
    if conf is None: return None,'no conformer'
    for atom in mol.GetAtoms():
        pos=conf.GetAtomPosition(atom.GetIdx())
        if not all(math.isfinite(v) for v in (pos.x,pos.y,pos.z)): return None,'non-finite coordinates'
    return mol,''

def write_csv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
    if OUT.exists(): raise RuntimeError(f'refusing to overwrite {OUT}')
    catalog=list(csv.DictReader((STAGE/'Ligase_Table/Database_Ready/Recruiter_Instance_Catalog.csv').open()))
    if len(catalog)!=1378: raise RuntimeError('unexpected active catalog count')
    tmp=Path(tempfile.mkdtemp(prefix='.v1-beta-r2-',dir=OUT.parent))
    audit=[]; manifest=[]; copied_canonical={}; counts=Counter()
    try:
        # R1 database and exact PDB assets are immutable byte-for-byte inputs.
        copy(R1/'database/E3_Ligandalyzer_v1.0_locked_20260908.sqlite',tmp/'database/E3_Ligandalyzer_v1.0_locked_20260908.sqlite')
        if sha(tmp/'database/E3_Ligandalyzer_v1.0_locked_20260908.sqlite')!=DB_SHA: raise RuntimeError('R1 SQLite SHA changed')
        for row in catalog:
            iid,ligase=row['Recruiter_Instance_ID'],row['Ligase']
            old=next(csv.DictReader((R1/'manifests/Web_Asset_Manifest.csv').open())) if False else None
            pdb=R1/'assets'/f'Ligases/{ligase}/PDB/{iid}.pdb'
            if not pdb.is_file(): raise RuntimeError(f'missing R1 PDB: {iid}')
            pdbrel=f'Ligases/{ligase}/PDB/{iid}.pdb'; pdbhash=copy(pdb,tmp/'assets'/pdbrel)
            source=Path(row['Source_SDF']) if row['Source_SDF'] else None
            kind='NO_VALIDATED_SDF_AVAILABLE'; sdfrel=''; sdfhash=''; warning=''; selected='NO'; reason=''
            if source and source.is_file():
                mol,error=sdf_ok(source)
                if not mol: kind='INVALID_OR_MISMATCHED_SDF'; reason=error
                elif '/Derived_Instance_SDF/' in str(source):
                    kind='EXACT_INSTANCE_SDF_AVAILABLE'; selected='YES'
                    sdfrel=f'Ligases/{ligase}/SDF/{iid}.sdf'; sdfhash=copy(source,tmp/'assets'/sdfrel)
                else:
                    kind='CANONICAL_ONLY_SDF_AVAILABLE'; selected='YES'
                    rel=f"chemistry/SDF/{row['Source_Entity_ID']}.sdf"
                    if rel not in copied_canonical: copied_canonical[rel]=copy(source,tmp/'assets'/rel)
                    sdfrel=rel; sdfhash=copied_canonical[rel]
            elif row['Recruiter_Entity_Type']=='BIRD_PRD':
                kind='WHOLE_PRD_NO_INSTANCE_SDF_EXPECTED'; reason='No registry-declared exact PRD SDF'
            counts[kind]+=1
            mol,error=sdf_ok(source) if source and source.is_file() else (None,reason)
            audit.append({'SDF_path':str(source or ''),'SHA256':sha(source) if source and source.is_file() else '', 'asset_category':kind,'Recruiter_Instance_ID':iid,'Recruiter_ID':row['Recruiter_ID'],'Source_Instance_Key':row['Source_Instance_Key'],'Ligase':ligase,'PDB_ID':row['pdb_id'],'Source_Entity_ID':row['Source_Entity_ID'],'source_provenance':row['Source_SDF'],'atom_count':mol.GetNumAtoms() if mol else '', 'heavy_atom_count':mol.GetNumHeavyAtoms() if mol else '', 'coordinate_dimensionality':'3D' if mol else '', 'sanitize_parse_status':'PASS' if mol else error, 'canonical_mapping_status':'AVAILABLE' if '/Derived_Instance_SDF/' in str(source or '') else 'NOT_APPLICABLE', 'selected_for_web_release':selected, 'rejection_reason':reason})
            manifest.append({'Recruiter_Instance_ID':iid,'Recruiter_ID':row['Recruiter_ID'],'Source_Instance_Key':row['Source_Instance_Key'],'Ligase':ligase,'pdb_id':row['pdb_id'],'Recruiter_Entity_Type':row['Recruiter_Entity_Type'],'Source_Entity_ID':row['Source_Entity_ID'],'PDB_Web_Path':pdbrel,'PDB_SHA256':pdbhash,'SDF_Source_Path':str(source or ''),'SDF_Web_Path':sdfrel,'SDF_SHA256':sdfhash,'SDF_Asset_Type':kind,'SDF_Provenance':str(source or ''),'SDF_Availability':'AVAILABLE' if sdfrel else 'UNAVAILABLE','PRD_ID':row['Source_Entity_ID'] if row['Recruiter_Entity_Type']=='BIRD_PRD' else '','Asset_Status':'PDB_READY'+('_SDF_READY' if sdfrel else ''),'Warnings':warning or reason})
        fields=list(manifest[0]); write_csv(tmp/'manifests/Web_Asset_Manifest.csv',manifest,fields)
        # R1 staging is historical candidate material.  Keep R2 audit products
        # outside it so a clean R2 assembly never alters an older candidate.
        write_csv(AUDIT/'V1_Beta_R2_Authoritative_SDF_Inventory.csv',audit,list(audit[0]))
        write_csv(AUDIT/'V1_Beta_R2_SDF_Coverage.csv',[{'Category':k,'Instances':v} for k,v in sorted(counts.items())],['Category','Instances'])
        release={'release_id':'v1.0-beta-r2-20260912','release_version':'1.0','release_status':'BETA','release_revision':2,'candidate_type':'web_asset_materialization_fix','database_cutoff_date':'2026-09-08','build_date':datetime.now(timezone.utc).isoformat(),'supersedes_candidate':'v1.0-locked-20260908-r1','database':{'relative_path':'database/E3_Ligandalyzer_v1.0_locked_20260908.sqlite','sha256':DB_SHA,'size_bytes':(tmp/'database/E3_Ligandalyzer_v1.0_locked_20260908.sqlite').stat().st_size},'assets':{'root':'assets','pdb_count':len(manifest),'exact_instance_sdf_count':counts['EXACT_INSTANCE_SDF_AVAILABLE'],'canonical_only_sdf_rows':counts['CANONICAL_ONLY_SDF_AVAILABLE'],'canonical_shared_sdf_count':len(copied_canonical),'no_validated_sdf_count':counts['NO_VALIDATED_SDF_AVAILABLE'],'sdf_inventory_audit':'Corpus_Audit/V1_Beta_R2_Authoritative_SDF_Inventory.csv'}}
        (tmp/'manifests/release_manifest.json').write_text(json.dumps(release,indent=2)+'\n'); (tmp/'release_manifest.json').write_text(json.dumps(release,indent=2)+'\n')
        (tmp/'manifests/Web_Asset_Orphan_Audit.csv').write_text('Asset_Type,Source_Path,Reason\n')
        (tmp/'BETA_RELEASE_RECEIPT.md').write_text(f'# V1 Beta R2 receipt\n\nSQLite is byte-identical to Beta R1: `{DB_SHA}`.\n\n'+json.dumps(dict(counts),indent=2)+'\n')
        files=sorted(p for p in tmp.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
        (tmp/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(tmp)}\n' for p in files))
        shutil.move(str(tmp),str(OUT)); print(json.dumps({'release':str(OUT),'counts':dict(counts),'canonical_shared':len(copied_canonical)},indent=2))
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True); raise
if __name__=='__main__': main()
