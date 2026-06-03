# 🧬 E3 Ligase Atlas Explorer — Modular Edition

**E3 Ligase Atlas Explorer** is an interactive and extensible web module for visualizing, comparing, and analyzing **E3 ligase–recruiter interactions** in the context of targeted protein degradation (TPD) and PROTAC design.

Built with a modern Python–Flask backend and a dynamic Tailwind + JavaScript frontend, it provides an intuitive interface for structural biologists, chemoinformaticians, and drug designers to explore PDB complexes, ligase scaffolds, and recruiter diversity in real time.

---

## 🚀 Key Features

* **Interactive Structural Viewer:**

  * Visualize 3D complexes directly in-browser using Mol*.
  * Highlight ligands, pockets, residues, and interfacial contacts dynamically.

* **Ligase & Recruiter Dashboard:**

  * Explore recruiter totals, class distributions, and scaffold diversity.
  * Filter and analyze by E3 ligase families such as CRBN, VHL, DCAF15, MDM2, KEAP1, and more.

* **Smart Visualization Modes:**

  * Toggle electrostatics, hydrophobicity, and color palettes for clarity.
  * Display hydrogen bonds, surfaces, and residue labels on demand.

* **Modular Template Architecture:**

  * HTML templates (`index.html`, `explorer.html`, `ligand.html`, etc.) for easy scaling.
  * API-ready for integration with ligand databases or AI-driven prediction tools.

* **Error Handling & UX Enhancements:**

  * Graceful 404 pages, missing-data alerts, and support contact fallback.
  * Designed for deployment on Flask servers or Hugging Face Spaces.

---

## 🧩 Project Structure

```
e3-ligase-atlas-explorer/
├── static/
│   └── style.css
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── explorer.html
│   ├── ligand.html
│   ├── scaffolds.html
│   └── missing_data.html
└── app.py
```

---

## 🧠 Scientific Context

This project builds upon the growing need for transparency and accessibility in **E3 ligase–recruiter interaction data**. By integrating curated PDB structures and visual analytics, it supports the design of next-generation degraders and molecular glues.

The modular edition enables community-driven contributions, simplified updates, and compatibility with AI workflows for molecular interaction prediction.

---

## 🧑‍💻 Getting Started

```bash
git clone https://github.com/YOUR_USERNAME/e3-ligase-module.git
cd e3-ligase-module
pip install -r requirements.txt
python app.py
```

Then open your browser at **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.

---

## 🌍 Citation & Attribution

If you use this work in research, please cite:

> Schulz, J.-M. (2025). *E3 Ligase Atlas Explorer — Modular Edition.* Mindful Diabetes Inc. & University of Miami.

---

## 💬 Contact

For questions, feedback, or collaboration:
📧 **[jxs794@miami.edu](mailto:jxs794@miami.edu)**
