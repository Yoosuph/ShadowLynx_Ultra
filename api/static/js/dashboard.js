/**
 * Dashboard initialization and chart rendering
 */

function initializeDashboard(priceData) {
    // Initialize charts
    initializePriceChart(priceData);
    initializeNetworkChart();
    initializeDexChart();
    
    // Start periodic updates
    startPeriodicUpdates();
}

function initializePriceChart(priceData) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    // Determine tokens to display
    const tokens = Object.keys(priceData);
    if (tokens.length === 0) {
        // No data available
        return;
    }
    
    // Prepare datasets
    const datasets = [];
    const colors = [
        '#4caf50', '#2196f3', '#ff9800', '#e91e63', '#9c27b0', 
        '#00bcd4', '#ffeb3b', '#795548', '#607d8b', '#3f51b5'
    ];
    
    tokens.forEach((token, index) => {
        // Get data for primary DEX (first one in the list)
        const tokenData = priceData[token];
        if (!tokenData || tokenData.length === 0) return;
        
        // Group by DEX to show multiple lines per token
        const dexMap = {};
        tokenData.forEach(entry => {
            if (!dexMap[entry.dex]) {
                dexMap[entry.dex] = [];
            }
            dexMap[entry.dex].push({
                x: entry.timestamp,
                y: entry.price
            });
        });
        
        // Create dataset for each DEX
        Object.keys(dexMap).forEach((dex, dexIndex) => {
            // Sort data points by timestamp
            const points = dexMap[dex].sort((a, b) => a.x - b.x);
            
            // Use a different shade of the same color for each DEX
            const baseColor = colors[index % colors.length];
            const opacity = 1 - (dexIndex * 0.2);
            const rgbColor = hexToRgb(baseColor);
            const color = `rgba(${rgbColor.r}, ${rgbColor.g}, ${rgbColor.b}, ${opacity})`;
            
            datasets.push({
                label: `${token} on ${dex}`,
                data: points,
                borderColor: color,
                backgroundColor: 'transparent',
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2
            });
        });
    });
    
    // Create chart
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'hour',
                        displayFormats: {
                            hour: 'HH:mm'
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: $${context.parsed.y.toFixed(4)}`;
                        }
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

function initializeNetworkChart() {
    const ctx = document.getElementById('networkChart').getContext('2d');
    
    // This would ideally come from an API call
    // For now, using sample data
    const data = {
        labels: ['BSC', 'Polygon'],
        datasets: [{
            data: [60, 40],
            backgroundColor: ['#F0B90B', '#8247E5'],
            hoverOffset: 4
        }]
    };
    
    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((value / total) * 100);
                            return `${context.label}: ${percentage}%`;
                        }
                    }
                }
            },
            cutout: '70%'
        }
    });
}

function initializeDexChart() {
    const ctx = document.getElementById('dexChart').getContext('2d');
    
    // This would ideally come from an API call
    // For now, using sample data
    const data = {
        labels: ['PancakeSwap', 'UniswapV3', 'SushiSwap', 'Other DEXs'],
        datasets: [{
            data: [40, 30, 20, 10],
            backgroundColor: ['#00c853', '#2196f3', '#e91e63', '#607d8b'],
            hoverOffset: 4
        }]
    };
    
    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((value / total) * 100);
                            return `${context.label}: ${percentage}%`;
                        }
                    }
                }
            },
            cutout: '70%'
        }
    });
}

function startPeriodicUpdates() {
    // Update live status indicator
    const liveStatusElement = document.getElementById('live-status');
    let isOnline = true;
    
    // Update status every 5 seconds
    setInterval(() => {
        if (liveStatusElement) {
            if (isOnline) {
                liveStatusElement.className = 'badge bg-success me-2';
                liveStatusElement.innerHTML = '<i data-feather="activity" class="feather-sm"></i> LIVE';
            } else {
                liveStatusElement.className = 'badge bg-danger me-2';
                liveStatusElement.innerHTML = '<i data-feather="wifi-off" class="feather-sm"></i> OFFLINE';
            }
            feather.replace();
        }
        
        // Check connection by making a simple request
        fetch('/api/status')
            .then(response => {
                isOnline = response.ok;
            })
            .catch(() => {
                isOnline = false;
            });
    }, 5000);
}

// Helper functions

function hexToRgb(hex) {
    // Remove # if present
    hex = hex.replace('#', '');
    
    // Parse hex values
    const bigint = parseInt(hex, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    
    return { r, g, b };
}
