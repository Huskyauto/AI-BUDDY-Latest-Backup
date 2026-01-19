// Initialize Chart.js visualization
document.addEventListener('DOMContentLoaded', function() {
    // Function to save mood
    window.saveMood = async function(mood, notes) {
        try {
            console.log('Saving mood:', { mood, notes });
            const response = await fetch('/api/save-mood', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ mood, notes })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || 'Failed to save mood');
            }

            console.log('Mood saved successfully:', data);

            // Refresh the mood chart
            await window.createMoodChart();

            // Show success message
            alert('Mood saved successfully!');

            return data;
        } catch (error) {
            console.error('Error saving mood:', error);
            alert('Failed to save mood: ' + error.message);
            throw error;
        }
    };

    // Function to fetch mood data
    async function fetchMoodData() {
        try {
            console.log('Fetching mood data from /api/mood-patterns...');
            const response = await fetch('/api/mood-patterns');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('Received mood data:', data);
            return data;
        } catch (error) {
            console.error('Error fetching mood data:', error);
            throw error;
        }
    }

    // Function to create the mood pattern chart
    window.createMoodChart = async function() {
        try {
            console.log('Starting to create mood chart...');
            const data = await fetchMoodData();

            // Clear any existing chart
            if (window.moodChart) {
                console.log('Destroying existing chart...');
                window.moodChart.destroy();
            }

            const ctx = document.getElementById('moodPatternChart');
            if (!ctx) {
                console.error('Could not find mood pattern chart canvas');
                return;
            }

            if (!data.dates || !data.values || data.dates.length === 0) {
                console.log('No mood data available, displaying message...');
                const context = ctx.getContext('2d');
                context.clearRect(0, 0, ctx.width, ctx.height);
                context.font = '14px Arial';
                context.textAlign = 'center';
                context.fillStyle = '#666';
                context.fillText('Start tracking your moods using the mood selector below to see your patterns.', ctx.width / 2, ctx.height / 2);
                return;
            }

            // Create gradient
            const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, 'rgba(71, 181, 172, 0.6)');
            gradient.addColorStop(1, 'rgba(71, 181, 172, 0.1)');

            window.moodChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.dates,
                    datasets: [{
                        label: 'Mood Pattern',
                        data: data.values,
                        fill: true,
                        backgroundColor: gradient,
                        borderColor: 'rgb(71, 181, 172)',
                        tension: 0.4,
                        pointBackgroundColor: 'rgb(71, 181, 172)',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 6,
                        pointHoverRadius: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(255, 255, 255, 0.9)',
                            titleColor: '#2D3748',
                            bodyColor: '#2D3748',
                            borderColor: 'rgba(71, 181, 172, 0.2)',
                            borderWidth: 1,
                            padding: 12,
                            displayColors: false,
                            callbacks: {
                                label: function(context) {
                                    const mood = data.moods[context.dataIndex];
                                    const value = context.raw;
                                    return `Mood: ${mood} (${value})`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 5,
                            ticks: {
                                stepSize: 1,
                                callback: function(value) {
                                    return ['Very Low', 'Low', 'Neutral', 'Good', 'Very Good'][value - 1] || '';
                                }
                            },
                            grid: {
                                display: true,
                                color: 'rgba(0, 0, 0, 0.05)'
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    }
                }
            });
            console.log('Mood chart created successfully');
        } catch (error) {
            console.error('Failed to create mood chart:', error);
            const ctx = document.getElementById('moodPatternChart');
            if (ctx) {
                const context = ctx.getContext('2d');
                context.clearRect(0, 0, ctx.width, ctx.height);
                context.font = '14px Arial';
                context.textAlign = 'center';
                context.fillStyle = '#666';
                context.fillText('Error loading mood data. Please try again later.', ctx.width / 2, ctx.height / 2);
            }
        }
    };

    // Automatically load the chart when the DOM is loaded
    window.createMoodChart();
    
    // Re-create chart when tab is shown
    const analyticsTab = document.querySelector('a[href="#analytics"]');
    if (analyticsTab) {
        analyticsTab.addEventListener('shown.bs.tab', function (e) {
            console.log('Analytics tab shown - loading chart automatically');
            window.createMoodChart();
        });
    }
});