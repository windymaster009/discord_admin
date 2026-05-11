const chartInstances = {};

const chartColors = {
    blurple: "#5865f2",
    green: "#3ba55d",
    yellow: "#faa61a",
    red: "#ed4245",
    text: "#dcddde",
    muted: "#8e9297",
    grid: "rgba(255, 255, 255, 0.08)"
};

function destroyChart(id) {
    if (chartInstances[id]) {
        chartInstances[id].destroy();
        delete chartInstances[id];
    }
}

function createChart(id, config) {
    const canvas = document.getElementById(id);

    if (!canvas || typeof Chart === "undefined") {
        return;
    }

    destroyChart(id);
    chartInstances[id] = new Chart(canvas, config);
}

function emptyLabels(labels) {
    return labels && labels.length ? labels : ["No data"];
}

function emptyValues(values) {
    return values && values.length ? values : [0];
}

function makeCharts() {
    const data = window.dashboardCharts || {};
    const memberTypes = data.memberTypes || {};
    const topRoles = data.topRoles || {};
    const joinActivity = data.joinActivity || {};

    Chart.defaults.color = chartColors.text;
    Chart.defaults.font.family = "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";

    createChart("memberTypeChart", {
        type: "doughnut",
        data: {
            labels: emptyLabels(memberTypes.labels),
            datasets: [{
                data: emptyValues(memberTypes.values),
                backgroundColor: [chartColors.green, chartColors.blurple],
                borderColor: "#1e1f22",
                borderWidth: 4,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "68%",
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        boxWidth: 10,
                        boxHeight: 10,
                        usePointStyle: true,
                        padding: 16
                    }
                }
            }
        }
    });

    createChart("topRoleChart", {
        type: "bar",
        data: {
            labels: emptyLabels(topRoles.labels),
            datasets: [{
                label: "Members",
                data: emptyValues(topRoles.values),
                backgroundColor: "rgba(88, 101, 242, 0.78)",
                borderColor: chartColors.blurple,
                borderWidth: 1,
                borderRadius: 8,
                maxBarThickness: 34
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: chartColors.muted,
                        maxRotation: 0,
                        autoSkip: true
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: chartColors.grid },
                    ticks: {
                        color: chartColors.muted,
                        precision: 0
                    }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });

    createChart("joinActivityChart", {
        type: "line",
        data: {
            labels: emptyLabels(joinActivity.labels),
            datasets: [{
                label: "Joins",
                data: emptyValues(joinActivity.values),
                borderColor: chartColors.yellow,
                backgroundColor: "rgba(250, 166, 26, 0.16)",
                borderWidth: 3,
                pointBackgroundColor: chartColors.yellow,
                pointBorderColor: "#1e1f22",
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.36
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: chartColors.muted }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: chartColors.grid },
                    ticks: {
                        color: chartColors.muted,
                        precision: 0
                    }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

document.addEventListener("DOMContentLoaded", makeCharts);
