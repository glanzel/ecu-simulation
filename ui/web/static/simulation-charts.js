(function () {
  var colors = [
    "#0d9488", "#6366f1", "#d97706", "#dc2626", "#7c3aed",
    "#059669", "#2563eb", "#db2777", "#4d7c0f", "#0891b2",
  ];

  function chartLabels(payload) {
    return payload.chartLabels || {};
  }

  function label(payload, key, fallback) {
    var labels = chartLabels(payload);
    return labels[key] || fallback;
  }

  function baseLineOptions(payload, yKey, yFallback) {
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
          title: { display: true, text: label(payload, "x_axis", "Month (simulation)"), font: { size: 11 } },
          ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 24, font: { size: 10 } },
        },
        y: {
          title: { display: true, text: label(payload, yKey, yFallback), font: { size: 11 } },
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
    var c3 = document.getElementById("chart-pct-vet-ziel");
    var c4 = document.getElementById("chart-price-by-boundary");
    if (c1) {
      new Chart(c1, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: label(payload, "mean_utilization_dataset", "Mean utilization"),
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
        options: baseLineOptions(payload, "mean_utilization_y", "Utilization"),
      });
    }
    if (c2) {
      new Chart(c2, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: label(payload, "bundle_ecu_T", "bundle_ecu_T"),
              data: payload.bundle_ecu_T,
              borderColor: colors[1],
              tension: 0.15,
              fill: false,
              pointRadius: 0,
              borderWidth: 2,
            },
            {
              label: label(payload, "ecu_ist_T", "ecu_ist_T"),
              data: payload.ecu_ist_T,
              borderColor: colors[2],
              tension: 0.15,
              fill: false,
              pointRadius: 0,
              borderWidth: 2,
            },
            {
              label: label(payload, "ecumenge_ziel_J_T", "ecumenge_ziel_J_T"),
              data: payload.ecumenge_ziel_J_T,
              borderColor: colors[3],
              tension: 0,
              fill: false,
              pointRadius: 0,
              borderWidth: 1.75,
              borderDash: [6, 4],
            },
            {
              label: label(payload, "ecumenge_ziel_sim_J_T", "ecumenge_ziel_sim_J_T"),
              data: payload.ecumenge_ziel_sim_J_T,
              borderColor: colors[4],
              tension: 0.15,
              fill: false,
              pointRadius: 0,
              borderWidth: 1.75,
              borderDash: [2, 3],
            },
            {
              label: label(payload, "ecumenge_T", "ecumenge_T"),
              data: payload.ecumenge_T,
              borderColor: colors[5],
              tension: 0.15,
              fill: false,
              pointRadius: 0,
              borderWidth: 1.75,
              borderDash: [1, 3],
            },
          ],
        },
        options: baseLineOptions(payload, "ecu_per_month_y", "ECU / month"),
      });
    }
    if (c3 && payload.pctVetZielSeries) {
      var ds3 = [];
      for (var i = 0; i < boundaries.length; i++) {
        var b = boundaries[i];
        var col = colors[i % colors.length];
        ds3.push({
          label: b.label || b.key,
          data: payload.pctVetZielSeries[i],
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
        options: baseLineOptions(payload, "pct_vet_ziel_y", "VEJ-Ist / VET target (%)"),
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
        options: baseLineOptions(payload, "price_y", "Shadow price (ECU / unit)"),
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
