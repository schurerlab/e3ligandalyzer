# ============================================================
# Ligase_DataDictionary.py
# ------------------------------------------------------------
# Comprehensive scientific metadata for all Ligase project
# datasets. Each entry explains what the datapoint represents,
# its scientific meaning, and why it is relevant for ligand–
# ligase interaction analysis and recruiter characterization.
# ============================================================

Ligase_DataDictionary = {
    # --------------------------------------------------------
    # CORE STRUCTURAL FIELDS
    # --------------------------------------------------------
    "Ligase": (
        "Name of the E3 ligase protein (e.g., CRBN, VHL, DCAF15, cIAP2). "
        "This identifies the ubiquitin ligase that recruits target proteins for degradation. "
        "Ligase identity defines the biological context of the ligand–protein interaction."
    ),
    "pdb_id": (
        "Protein Data Bank (PDB) identifier for the structure. "
        "Each code corresponds to an experimentally determined 3D structure entry. "
        "This allows traceability to crystallographic data sources and structural validation."
    ),
    "Ligand": (
        "Three-letter residue code (or short identifier) for the bound small molecule ligand. "
        "This is derived from the PDB file and used to associate structural data with chemical metadata."
    ),
    "Residue_ID": (
        "Residue number assigned to the ligand in the PDB structure. "
        "Serves as a spatial index to link ligand atoms with binding site residues during analysis."
    ),
    "Variant": (
        "Variant index used when multiple versions of the same ligand occur in the same or alternate structures. "
        "A value of 1 indicates the default conformation; higher values correspond to alternate binding poses."
    ),
    "Chain": (
        "Identifier for the protein chain (A, B, C, etc.) that the ligand interacts with. "
        "Important for complexes containing multiple chains or ligase–target–linker assemblies."
    ),
    "atom_id": "Serial number of the atom in the PDB file for coordinate reference.",
    "exact_atom": (
        "Atom label within the PDB (e.g., C1, O2, N3). "
        "Used to map experimental coordinates to chemical atoms for 3D visualization and mapping."
    ),
    "atom_type": (
        "Elemental identity (C, N, O, S, Cl, etc.) of the atom. "
        "This defines the chemical nature of the atom and determines its bonding and polarity."
    ),
    "x": "X-coordinate of the atom in Ångstroms (Å).",
    "y": "Y-coordinate of the atom in Ångstroms (Å).",
    "z": "Z-coordinate of the atom in Ångstroms (Å).",
    "Exposure_A2": (
        "Solvent-accessible surface area (SASA) of an individual atom, measured in square Ångstroms. "
        "Quantifies how exposed that atom is to solvent, reflecting pocket burial and binding tightness."
    ),

    # --------------------------------------------------------
    # LIGAND METADATA (CHEMICAL IDENTITY)
    # --------------------------------------------------------
    "Name": (
        "Full IUPAC or common name of the ligand. "
        "Provides a human-readable identifier of the compound."
    ),
    "Formula": (
        "Molecular formula showing elemental composition (e.g., C13H10N2O4). "
        "Useful for verifying elemental balance, molecular weight, and stoichiometry."
    ),
    "Type": (
        "Classification of the ligand entity within the PDB entry. "
        "Usually 'non-polymer' for small molecules, but may include 'peptide' or 'polymer' for larger recruiters."
    ),
    "SMILES": (
        "Simplified Molecular Input Line Entry System representation of the 2D structure. "
        "Encodes connectivity and stereochemistry in text format for computational processing."
    ),
    "Canonical_SMILES": (
        "Canonicalized version of the SMILES string ensuring a unique atom ordering. "
        "This is used for consistent fingerprinting, descriptor generation, and deduplication."
    ),
    "InChI": (
        "IUPAC International Chemical Identifier. "
        "A standardized string encoding atom connectivity, charge, and stereochemistry. "
        "Useful for cross-database comparison and ensuring structure identity."
    ),
    "InChIKey": (
        "Short hashed form of the InChI used as a unique, searchable identifier. "
        "Ideal for indexing and web-based lookup of ligand data."
    ),
    "Formal_Charge": (
        "Net formal charge on the molecule, computed from valence rules. "
        "Affects molecular interactions, binding affinity, and solubility."
    ),
    "Atom_Count": (
        "Total number of atoms in the molecule (including hydrogens). "
        "Provides a general measure of molecular size and complexity."
    ),
    "Chiral_Atom_Count": (
        "Number of stereogenic (chiral) atoms in the molecule. "
        "Chirality plays a major role in selectivity and biological recognition."
    ),
    "Bond_Count": "Total number of covalent bonds in the molecule.",
    "Aromatic_Bond_Count": (
        "Number of aromatic bonds with delocalized π-electrons. "
        "High aromaticity often relates to rigidity and π–π stacking capacity."
    ),

    # --------------------------------------------------------
    # SASA SUMMARY AND COMPLEX PROPERTIES
    # --------------------------------------------------------
    "Recruiter_Class": (
        "Functional or mechanistic class of the recruiter ligand, such as IMiD-type (CRBN binders), "
        "VHL-type, or IAP-type ligands. Used to categorize recruiters by ligase recognition motif."
    ),
    "Total_atoms": "Total number of atoms within the ligand (same as Atom_Count but in the structural context).",
    "Exposed_atoms": (
        "Number of ligand atoms with measurable solvent exposure (SASA > 0 Å²). "
        "Indicates how much of the ligand remains solvent-accessible after complex formation."
    ),
    "SASA_in_complex_A2": (
        "Total solvent-accessible surface area of the entire ligand when bound to the ligase, in Å². "
        "Provides an absolute measure of ligand burial and pocket engagement."
    ),
    "%Exposed": (
        "Percentage of ligand atoms that remain solvent-accessible. "
        "Helps distinguish surface-bound ligands from deeply buried binders."
    ),
    "%Buried": (
        "Percentage of ligand atoms buried within the protein binding site (100 − %Exposed). "
        "A proxy for binding pocket depth and ligand burial efficiency."
    ),
    "MW": (
        "Molecular weight (Daltons). "
        "Correlates with molecular size, permeability, and typically the upper bound for oral bioavailability."
    ),

    # --------------------------------------------------------
    # RDKit DESCRIPTORS AND COMPUTED MOLECULAR PROPERTIES
    # --------------------------------------------------------
    "LogP": (
        "Octanol–water partition coefficient (log P), a measure of hydrophobicity. "
        "Higher values imply lipophilicity; moderate values (1–3) often favor permeability and balance solubility."
    ),
    "TPSA": (
        "Topological Polar Surface Area (Å²), quantifying the surface contributed by polar atoms (O, N, etc.). "
        "Strongly correlates with passive membrane permeability; TPSA ≤ 140 Å² is favorable for oral absorption."
    ),
    "HBA": "Number of hydrogen bond acceptors, typically heteroatoms with lone pairs (O, N, S).",
    "HBD": "Number of hydrogen bond donors (e.g., –OH, –NH groups). Influences solubility and binding affinity.",
    "Rotatable_Bonds": (
        "Count of freely rotatable single bonds. "
        "Reflects conformational flexibility; lower values generally improve binding enthalpy and metabolic stability."
    ),
    "Ring_Count": "Total number of ring systems (both aromatic and aliphatic) in the molecule.",
    "Aromatic_Rings": "Number of aromatic rings; contributes to π-stacking and hydrophobic interactions.",
    "Fraction_CSP3": (
        "Fraction of sp³-hybridized carbons, ranging from 0 (planar) to 1 (fully saturated). "
        "High Fraction_CSP3 indicates 3D character; correlated with improved solubility and reduced promiscuity."
    ),
    "Heavy_Atom_Count": "Count of all non-hydrogen atoms; used in normalizing other properties (e.g., ligand efficiency).",
    "Chiral_Atoms": (
        "Number of atoms acting as stereocenters. "
        "Higher counts imply structural complexity and potential for enantioselective binding."
    ),
    "QED": (
        "Quantitative Estimate of Drug-likeness (0–1). "
        "Combines molecular weight, lipophilicity, polarity, and aromaticity into a single continuous index. "
        "High QED (>0.6) typically indicates favorable physicochemical balance."
    ),
    "BertzCT": (
        "Bertz complexity index, a topological measure combining atom count, bonding patterns, and symmetry. "
        "Higher values indicate structural diversity and synthetic richness."
    ),
    "HallKierAlpha": (
        "Molecular descriptor related to molecular shape and polarizability, derived from valence and topology. "
        "Useful for comparing flexibility and shape variance across recruiters."
    ),
    "Kappa1": "First-order Kier shape index — quantifies overall molecular size and branching.",
    "Kappa2": "Second-order Kier shape index — sensitive to cyclic vs. acyclic features.",
    "Kappa3": "Third-order Kier shape index — captures higher-order 3D molecular shape attributes.",
    "NumSpiroAtoms": (
        "Number of spiro atoms (atoms shared by two non-fused rings). "
        "Indicates 3D complexity; spiro centers can improve rigidity and selectivity."
    ),
    "NumBridgeheadAtoms": (
        "Number of bridgehead atoms shared across fused rings. "
        "These contribute to scaffold rigidity and define non-planar architectures."
    ),
    "NumAliphaticRings": "Count of non-aromatic (aliphatic) rings in the molecule.",
    "NumAromaticRings": "Count of aromatic rings; typically aligns with Aromatic_Rings.",
    "NumSaturatedRings": "Number of fully saturated rings; contributes to flexibility and solubility.",
    "NumHeteroAtoms": (
        "Number of heteroatoms (atoms other than carbon). "
        "Heteroatoms increase polarity, hydrogen bonding, and electronic diversity."
    ),
    "MolMR": (
        "Molar refractivity, proportional to polarizability and volume. "
        "Correlates with van der Waals interactions and molecular packing potential."
    ),
    "SA_Score": (
        "Synthetic Accessibility (SA) score, ranging from ~1 (easy to synthesize) to ~10 (very difficult). "
        "Combines fragment rarity and structural complexity. "
        "Useful for prioritizing molecules that are both potent and practically synthesizable."
    ),

    # --------------------------------------------------------
    # SCAFFOLD MAPPING AND DIVERSITY METRICS
    # --------------------------------------------------------
    "Scaffold_ID": (
        "Unique scaffold identifier for a given ligase, generated as 'Ligase_SCAF_N' or hashed form. "
        "Represents the Bemis–Murcko scaffold — the molecule’s core ring/linker framework. "
        "Used to group recruiters by structural core for diversity and clustering analyses."
    ),
    "Scaffold_SMILES": (
        "Canonical SMILES of the Bemis–Murcko scaffold, representing the molecule’s minimal core skeleton. "
        "Provides a standardized representation for comparing chemotypes across ligases."
    ),
    "Scaffold_Hash": (
        "Deterministic hash derived from either the scaffold SMILES or raw molecule SMILES. "
        "Ensures each scaffold remains uniquely identifiable even across datasets."
    ),
    "Unique_Scaffolds": (
        "Count of distinct scaffolds found within a ligase’s recruiter pool. "
        "Measures the chemical diversity of recruiters targeting that ligase."
    ),
    "Total_Recruiters": (
        "Total number of recruiter compounds analyzed per ligase. "
        "Used to normalize scaffold diversity and compute diversity indices."
    ),
    "Diversity_Score": (
        "Ratio of unique scaffolds to total recruiters for a given ligase. "
        "A proxy for chemical space richness — high values indicate broad scaffold diversity."
    ),
    "Shannon_Index": (
        "Shannon entropy of recruiter distribution per scaffold. "
        "Quantifies scaffold evenness and diversity within a ligase's chemical space."
    ),
    "Recruiter_Count": (
        "Number of recruiters assigned to each scaffold. "
        "Represents scaffold recurrence or dominance within a ligase’s recruiter space."
    ),

    # --------------------------------------------------------
    # ADVANCED / FUTURE DATA COLUMNS
    # --------------------------------------------------------
    "Scaffold_Class": (
        "Assigned chemical scaffold family (e.g., phthalimide, hydroxyproline, benzodiazepine). "
        "Can be determined via SMARTS-based substructure matching or cheminformatic clustering."
    ),
    "Scaffold_Center_of_Mass_X": "X-coordinate of the scaffold’s geometric center for 3D visualization.",
    "Scaffold_Center_of_Mass_Y": "Y-coordinate of the scaffold’s geometric center for 3D visualization.",
    "Scaffold_Center_of_Mass_Z": "Z-coordinate of the scaffold’s geometric center for 3D visualization.",
    "Ligase_Scaffold_Connectivity": (
        "Network connectivity metric indicating how many ligases share the same scaffold. "
        "Higher values imply scaffold promiscuity and cross-ligase usability."
    ),
    "Recruiter_Density_Score": (
        "Normalized recruiter count per scaffold (Recruiter_Count / Total_Recruiters). "
        "Highlights scaffolds that dominate the recruiter pool for a given ligase."
    ),

    # --------------------------------------------------------
    # RULE-BASED FILTERS AND QUALITY ALERTS
    # --------------------------------------------------------
    "Lipinski_Pass": (
        "Boolean flag indicating compliance with Lipinski's 'Rule of Five'. "
        "MW ≤ 500, LogP ≤ 5, HBD ≤ 5, HBA ≤ 10 — used to predict oral bioavailability."
    ),
    "Veber_Pass": "True if Veber’s rule (TPSA ≤ 140 Å² and ≤ 10 rotatable bonds) is satisfied.",
    "Egan_Pass": (
        "True if compound passes the Egan filter, balancing LogP and TPSA for good permeability and absorption."
    ),
    "Ghose_Pass": (
        "True if compound satisfies Ghose criteria (160 < MW < 480, 40 < MR < 130, 0.4 < LogP < 5.6, "
        "and atom count between 20 and 70)."
    ),
    "Muegge_Pass": (
        "True if molecule falls within Muegge’s 'drug-like' chemical space. "
        "Used for broad chemical quality screening."
    ),
    "PAINS_Hits": (
        "List of Pan-Assay Interference structural alerts. "
        "PAINS are known promiscuous chemotypes prone to assay artifacts."
    ),
    "Brenk_Hits": (
        "List of Brenk structural alerts identifying chemically unstable or reactive moieties."
    ),

    # --------------------------------------------------------
    # IDENTIFIERS AND LINKERS
    # --------------------------------------------------------
    "RECRUITER_CODE": (
        "Unique internal code for recruiter compounds, combining ligase identity "
        "and ligand index (e.g., CRBN_L00045). Acts as the unifying key across all datasets."
    ),
}

# ------------------------------------------------------------
# Optional JSON export
# ------------------------------------------------------------
if __name__ == "__main__":
    import json
    with open("Ligase_DataDictionary.json", "w") as f:
        json.dump(Ligase_DataDictionary, f, indent=4)
    print("✅ Saved Ligase_DataDictionary.json")
