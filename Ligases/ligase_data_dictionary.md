# 🧬 Ligase Data Dictionary  
*Comprehensive definitions and scientific meanings for all fields in the Ligase Project datasets.*

---

## 🧩 Core Structural Fields

| **Field** | **Description** |
|------------|-----------------|
| **Ligase** | Name of the E3 ligase protein (e.g., CRBN, VHL, DCAF15, cIAP2). Identifies the ubiquitin ligase responsible for substrate recruitment in degradation complexes. |
| **pdb_id** | Protein Data Bank identifier of the structure. Each entry corresponds to a resolved 3D structure. Enables validation and traceability. |
| **Ligand** | Three-letter residue code or short identifier for the bound small molecule ligand. Derived from the PDB. |
| **Residue_ID** | Residue number assigned to the ligand in the structure. Used for mapping ligand atoms to binding site residues. |
| **Variant** | Variant index (1 = primary; >1 = alternate conformer). Distinguishes between multiple poses or ligands in the same complex. |
| **Chain** | Chain ID (A, B, etc.) indicating the protein chain bound to the ligand. Important for complexes with multiple subunits. |
| **atom_id** | Serial number of the atom in the PDB file. |
| **exact_atom** | Atom label (e.g., C1, O2, N3) from the PDB entry. |
| **atom_type** | Element type (C, N, O, S, Cl, etc.) of the atom. Defines bonding and chemical behavior. |
| **x**, **y**, **z** | Cartesian coordinates of the atom in Ångstroms. Defines spatial positioning within the protein-ligand complex. |
| **Exposure_A2** | Solvent-accessible surface area (Å²) of each atom. Indicates solvent exposure vs. burial in the binding pocket. |

---

## 💊 Ligand Metadata (Chemical Identity)

| **Field** | **Description** |
|------------|-----------------|
| **Name** | Full IUPAC or common name of the ligand. |
| **Formula** | Molecular formula indicating elemental composition. |
| **Type** | Ligand entity classification (e.g., non-polymer, peptide). |
| **SMILES** | 2D text representation of chemical connectivity and stereochemistry. |
| **Canonical_SMILES** | Canonicalized form ensuring consistent atom ordering for fingerprinting and deduplication. |
| **InChI / InChIKey** | International Chemical Identifier and its hashed key. Universal reference for structure identity. |
| **Formal_Charge** | Net formal charge. Influences binding affinity and solubility. |
| **Atom_Count** | Total number of atoms (including hydrogens). |
| **Chiral_Atom_Count** | Count of stereogenic atoms. Relates to enantioselectivity and structural complexity. |
| **Bond_Count** | Total number of bonds. |
| **Aromatic_Bond_Count** | Number of aromatic bonds with delocalized π-electrons. Linked to planarity and rigidity. |

---

## 🌊 SASA and Complex Properties

| **Field** | **Description** |
|------------|-----------------|
| **Recruiter_Class** | Functional class (e.g., IMiD, VHL-type). Groups recruiters by ligase recognition motif. |
| **Total_atoms** | Total ligand atoms within structural context. |
| **Exposed_atoms** | Count of solvent-exposed atoms (SASA > 0 Å²). |
| **SASA_in_complex_A2** | Total solvent-accessible surface area of ligand in the complex (Å²). |
| **%Exposed / %Buried** | Percentage of solvent-accessible vs. buried ligand atoms. Indicates binding depth. |
| **MW** | Molecular weight (Daltons). Size indicator relevant to permeability and bioavailability. |

---

## ⚗️ RDKit Descriptors and Computed Properties

| **Field** | **Description** |
|------------|-----------------|
| **LogP** | Octanol–water partition coefficient. Measures hydrophobicity/lipophilicity. |
| **TPSA** | Topological polar surface area (Å²). Predicts passive permeability and oral absorption. |
| **HBA / HBD** | Hydrogen bond acceptor/donor counts. Control solubility and binding potential. |
| **Rotatable_Bonds** | Number of rotatable single bonds. Reflects flexibility. |
| **Ring_Count / Aromatic_Rings** | Total and aromatic ring counts. Capture rigidity and π-interactions. |
| **Fraction_CSP3** | Fraction of sp³ carbons (0–1). Quantifies 3D saturation; higher = more drug-like. |
| **Heavy_Atom_Count** | Number of non-hydrogen atoms. Used for normalization. |
| **Chiral_Atoms** | Count of stereocenters. Indicates complexity and selectivity. |
| **QED** | Quantitative Estimate of Drug-likeness (0–1). Combines key physicochemical metrics. |
| **BertzCT** | Bertz complexity index. Measures structural richness and symmetry. |
| **HallKierAlpha / Kappa1–3** | Molecular shape and topology indices capturing branching and 3D form. |
| **NumSpiroAtoms / NumBridgeheadAtoms** | Count of spiro and bridgehead atoms — structural rigidity measures. |
| **NumAliphatic / NumAromatic / NumSaturatedRings** | Detailed ring composition. |
| **NumHeteroAtoms** | Non-carbon atom count — reflects polarity and interaction potential. |
| **MolMR** | Molar refractivity; relates to volume and polarizability. |
| **SA_Score** | Synthetic accessibility score (1–10). Low = easier synthesis. |

---

## 🧱 Scaffold Mapping and Diversity Metrics

| **Field** | **Description** |
|------------|-----------------|
| **Scaffold_ID** | Unique scaffold label per ligase (`Ligase_SCAF_N` or hash). Represents the Bemis–Murcko scaffold core. |
| **Scaffold_SMILES** | Canonical SMILES of the extracted scaffold (ring + linker framework). |
| **Scaffold_Hash** | Deterministic hash derived from scaffold SMILES. Ensures unique indexing across datasets. |
| **Unique_Scaffolds** | Number of distinct scaffolds within each ligase. Indicates structural diversity. |
| **Total_Recruiters** | Total recruiter ligands per ligase. Used for normalization of diversity scores. |
| **Diversity_Score** | Ratio of unique scaffolds to total recruiters (Unique/Total). A simple diversity metric. |
| **Shannon_Index** | Shannon entropy (H = –Σ pᵢ log pᵢ) over recruiter distribution. Measures scaffold evenness and diversity. |
| **Recruiter_Count** | Number of recruiters mapped to a scaffold (scaffold recurrence). |

---

## 🧠 Advanced / Future Columns

| **Field** | **Description** |
|------------|-----------------|
| **Scaffold_Class** | Scaffold family name (e.g., phthalimide, hydroxyproline). Assigned via SMARTS or clustering. |
| **Scaffold_Center_of_Mass_X/Y/Z** | 3D coordinates of the scaffold centroid. Useful for visualization alignment. |
| **Ligase_Scaffold_Connectivity** | Network connectivity metric representing how many ligases share the scaffold (cross-ligase reuse). |
| **Recruiter_Density_Score** | Normalized recruiter density per scaffold (Recruiter_Count / Total_Recruiters). Highlights dominant chemotypes. |

---

## ⚖️ Rule-Based Filters and Quality Alerts

| **Field** | **Description** |
|------------|-----------------|
| **Lipinski_Pass** | Pass/fail for Lipinski’s “Rule of Five”. Predicts oral drug-likeness. |
| **Veber_Pass** | Veber rule compliance (TPSA ≤ 140 Å² and ≤10 rotatable bonds). |
| **Egan_Pass** | Egan filter for permeability and absorption balance. |
| **Ghose_Pass** | Ghose filter compliance (based on MW, LogP, MR, atom count). |
| **Muegge_Pass** | Muegge filter compliance for general drug-like space. |
| **PAINS_Hits** | List of Pan-Assay Interference substructures — promiscuous motifs to avoid. |
| **Brenk_Hits** | List of reactive or toxic substructures from Brenk filters. |

---

## 🧩 Identifiers and Linkers

| **Field** | **Description** |
|------------|-----------------|
| **RECRUITER_CODE** | Unique internal code linking recruiter to ligase (e.g., CRBN_L00045). Serves as the cross-table key. |

---

## 📊 Data Tables Overview

| **Table Name** | **Description** |
|-----------------|-----------------|
| **Ligase_Ligands_Smiles_3DMapped.csv** | Full atom-level mapping between 3D structure (PDB) and 2D chemical identity (SMILES). |
| **Ligase_Ligand_Metadata.csv** | High-level chemical and structural identity of ligands. |
| **Ligase_Ligand_SASA_summary.csv** | Solvent-accessibility and burial metrics per ligand. |
| **Ligase_Chemical_Descriptors.csv** | RDKit-derived molecular descriptors and drug-likeness metrics. |
| **Ligase_Recruiters_Scaffold.csv** | Recruiter-to-scaffold mapping for structural clustering. |
| **Ligase_Scaffold_Summary.csv** | Per-ligase scaffold diversity metrics (unique scaffolds, diversity score, entropy). |
| **Ligase_Scaffold_Frequency.csv** | Number of recruiters per scaffold for frequency visualization. |

---

*Compiled by Joseph-Michael Schulz (University of Miami, 2025)*  
*Ligase Database Project – Structural, Chemical, and Scaffold-Level Characterization*
