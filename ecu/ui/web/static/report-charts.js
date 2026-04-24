(function () {
  var colors = [
    "#0d9488", "#6366f1", "#d97706", "#dc2626", "#7c3aed",
    "#059669", "#2563eb", "#db2777", "#4d7c0f", "#0891b2",
  ];

  function baseLineOptions(yTitle) {
    return {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 2,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { bodyFont: { size: 11 }, titleFont: { size: 11 } },
      },
      scales: {
        x: {
          title: { display: true, text: "Monat (Simulation)", font: { size: 11 } },
          ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 24, font: { size: 10 } },
        },
        y: {
          title: { display: true, text: yTitle, font: { size: 11 } },
          ticks: { font: { size: 10 } },
        },
      },
    };
  }

  function init() {
    var el = document.getElementById("ecu-report-chart-data");
    if (!el || typeof el.textContent !== "string") {
      return;
    }
    var text = el.textContent.trim();
    if (!text) {
      return;
    }
    var payload;
    try {
      payload = JSON.parse(text);
    } catch (e) {
      return;
    }
    if (!payload.labels || !payload.labels.length) {
      return;
    }
    if (typeof Chart === "undefined") {
      return;
    }
    var labels = payload.labels;
    var boundaries = payload.boundaries || [];
    var c1 = document.getElementById("chart-mean-utilization");
    var c2 = document.getElementById("chart-ecu-totals");
    var c3 = document.getElementById("chart-pct-vet-by-boundary");
    var c4 = document.getElementById("chart-price-by-boundary");
    if (c1) {
      new Chart(c1, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Mittlere Auslastung (Ø Konsum / VET)",
              data: payload.meanUtilization,
              borderColor: colors[0],
              backgroundColor: "rgba(13,148,136,0.08)",
              tension: 0.15,
              fill: false,
              pointRadius: 0,
              borderWidth: 2,
            },
          ],
        },
        options: baseLineOptions("Auslastung (ohne Einheit, kann > 1)"),
      });
    }
    if (c2) {
      new Chart(c2, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Σ p·VEJ (Rahmen, ECU/Monat)",
              data: payload.bundleEcu,
              borderColor: colors[1],
              tension: 0.15,
              fill: false,
              pointRadius: 0,
              borderWidth: 2,
            },
            {
              label: "Σ p·Konsum (verbuchte ECU/Monat)",
              data: payload.ecuExpenditure,
              borderColor: colors[2],
              tension: 0.15,
              fill: false,
              pointRadius: 0,
              borderWidth: 2,
            },
          ],
        },
        options: baseLineOptions("ECU pro Monat"),
      });
    }
    if (c3 && payload.pctVetSeries) {
      var ds3 = [];
      for (var i = 0; i < boundaries.length; i++) {
        var b = boundaries[i];
        var col = colors[i % colors.length];
        ds3.push({
          label: b.label || b.key,
          data: payload.pctVetSeries[i],
          borderColor: col,
          backgroundColor: "transparent",
          tension: 0.15,
          fill: false,
          pointRadius: 0,
          borderWidth: 1.5,
        });
      }
      new Chart(c3, {
        type: "line",
        data: { labels: labels, datasets: ds3 },
        options: baseLineOptions("Konsum / VET (%)"),
      });
    }
    if (c4 && payload.priceSeries) {
      var ds4 = [];
      for (var j = 0; j < boundaries.length; j++) {
        var b2 = boundaries[j];
        var col2 = colors[j % colors.length];
        ds4.push({
          label: b2.label || b2.key,
          data: payload.priceSeries[j],
          borderColor: col2,
          backgroundColor: "transparent",
          tension: 0.15,
          fill: false,
          pointRadius: 0,
          borderWidth: 1.5,
        });
      }
      new Chart(c4, {
        type: "line",
        data: { labels: labels, datasets: ds4 },
        options: baseLineOptions("Schattenpreis (ECU / Einheit)"),
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
