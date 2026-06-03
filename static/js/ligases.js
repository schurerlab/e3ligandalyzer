document.addEventListener("DOMContentLoaded", async () => {
  const tableBody = document.getElementById("ligaseBody");
  const plotContainer = document.getElementById("plotContainer");
  const plotTitle = document.getElementById("plotTitle");

  // Fetch ligases (from the new ELiAH database endpoint if available)
  const res = await fetch("/api/eliah/ligases");

  const ligases = res ? await res.json() : [];

  // Populate table
  tableBody.innerHTML = ligases.map(l => `
    <tr class="hover:bg-slate-800 cursor-pointer" data-gene="${l.GeneSymbol}">
      <td class="py-2 px-4">${l.LigaseName || '-'}</td>
      <td class="py-2 px-4 text-sky-300">${l.GeneSymbol || '-'}</td>
      <td class="py-2 px-4">${l.Class || '-'}</td>
      <td class="py-2 px-4">${l.SubstrateCount || '-'}</td>
      <td class="py-2 px-4 text-xs">${l.Source || '-'}</td>
    </tr>
  `).join("");

  // Add click listeners for expression plots
  tableBody.querySelectorAll("tr").forEach(row => {
    row.addEventListener("click", async () => {
      const gene = row.dataset.gene;
      plotTitle.textContent = `Gene Expression — ${gene}`;
      plotContainer.classList.remove("hidden");

      const exprRes = await fetch(`/api/eliah/expression/${gene}`);

      const exprData = await exprRes.json();

      const trace = {
        x: exprData.map(d => d.Sample),
        y: exprData.map(d => d.Z_score),
        type: "bar",
        marker: { color: "rgba(56,189,248,0.8)" }
      };

      Plotly.newPlot("genePlot", [trace], {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#e2e8f0" },
        margin: { t: 40, l: 50, r: 20, b: 120 }
      });
    });
  });
});
