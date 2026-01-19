let weightChart = null; // Global variable to store the chart instance

document.addEventListener('DOMContentLoaded', async function() {
    // Add loading state to prevent premature display
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.style.visibility = 'hidden';
    }

    try {
        console.log('Initializing food tracker...');

        // Initialize displays with the server-provided initial data
        if (window.initialData) {
            updateDisplays(window.initialData);
            updateWellnessQuote(window.initialData.quote);

            // Initialize weight chart with initial data if available
            if (window.initialData.weightHistory) {
                console.log('Initializing weight chart with initial data');
                await initializeWeightChart(window.initialData.weightHistory);
            } else {
                // If no weight history in initial data, fetch it
                console.log('Fetching weight history data');
                await updateWeightHistory();
            }
        }

        // Set up form submission handlers
        const weightForm = document.getElementById('weight-log-form');
        if (weightForm) {
            weightForm.addEventListener('submit', handleWeightSubmit);
        }

        const foodLogForm = document.getElementById('food-log-form');
        if (foodLogForm) {
            foodLogForm.addEventListener('submit', handleFoodLogSubmit);
        }

        // Add water settings form handler
        const waterSettingsForm = document.getElementById('weight-form');
        if (waterSettingsForm) {
            waterSettingsForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const weight = parseFloat(document.getElementById('weight').value);

                try {
                    const response = await fetch('/api/update-water-settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ weight })
                    });

                    const data = await response.json();
                    if (data.status === 'success') {
                        // Update water goal display
                        const waterGoalElement = document.getElementById('current-water-goal');
                        if (waterGoalElement) {
                            waterGoalElement.textContent = data.waterGoal.toFixed(1);
                        }

                        // Update calorie goal display
                        const calorieGoalElements = document.querySelectorAll('#calorie-goal');
                        calorieGoalElements.forEach(element => {
                            if (element) {
                                element.textContent = Math.round(data.calorieGoal);
                            }
                        });

                        // Update progress bars
                        updateProgress();
                    } else {
                        throw new Error(data.message || 'Failed to update settings');
                    }
                } catch (error) {
                    console.error('Error updating settings:', error);
                    alert('Error updating settings: ' + error.message);
                }
            });
        }

        // Water goal direct update handler
        const waterGoalForm = document.getElementById('water-goal-form');
        if (waterGoalForm) {
            waterGoalForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const waterGoal = parseFloat(document.getElementById('water-goal-input').value);

                try {
                    const response = await fetch('/api/update-water-settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ waterGoal })
                    });

                    const data = await response.json();
                    if (data.status === 'success') {
                        // Update water goal displays
                        const waterGoalElements = document.querySelectorAll('#water-goal, #current-water-goal');
                        waterGoalElements.forEach(element => {
                            if (element) {
                                element.textContent = data.waterGoal.toFixed(1);
                            }
                        });

                        // Update progress bars
                        updateProgress();
                    } else {
                        throw new Error(data.message || 'Failed to update water goal');
                    }
                } catch (error) {
                    console.error('Error updating water goal:', error);
                    alert('Error updating water goal: ' + error.message);
                }
            });
        }


        // Start periodic updates
        setInterval(checkDayChange, 60000);

        // Add visibility change listener
        document.addEventListener('visibilitychange', async function() {
            if (!document.hidden) {
                console.log('Tab became visible, updating data...');
                await updateDailySummary();
            }
        });

        console.log('Food tracker initialized successfully');

        // Now show the content
        if (mainContent) {
            mainContent.style.visibility = 'visible';
        }
    } catch (error) {
        console.error('Error initializing food tracker:', error);
        // Show error state
        if (mainContent) {
            mainContent.style.visibility = 'visible';
        }
    }
});

// Water tracking helper functions
function incrementWater() {
    const waterAmount = document.getElementById('water-amount');
    const currentValue = parseFloat(waterAmount.value) || 0;
    waterAmount.value = (currentValue + 1).toString();
}

function decrementWater() {
    const waterAmount = document.getElementById('water-amount');
    const currentValue = parseFloat(waterAmount.value) || 0;
    waterAmount.value = Math.max(0, currentValue - 1).toString();
}

async function logWater() {
    const amount = parseFloat(document.getElementById('water-amount').value);

    if (!amount || amount <= 0) {
        alert('Please enter a valid water amount');
        return;
    }

    try {
        console.log('Submitting water log:', amount);
        const response = await fetch('/api/log-water', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ amount })
        });

        const data = await response.json();
        console.log('Water log response:', data);

        if (data.status === 'success') {
            // Reset input
            document.getElementById('water-amount').value = '0';
            // Update daily summary to refresh all displays
            await updateDailySummary();
        } else {
            throw new Error(data.message || 'Failed to log water');
        }
    } catch (error) {
        console.error('Error logging water:', error);
        alert('Error logging water intake: ' + (error.message || 'Please try again'));
    }
}

// Weight chart functionality
async function initializeWeightChart(data) {
    console.log('Initializing weight chart with data:', data);
    const chartCanvas = document.getElementById('weightChart');

    if (!chartCanvas) {
        console.error('Weight chart canvas not found');
        return;
    }

    try {
        if (!data || !Array.isArray(data) || data.length === 0) {
            console.log('No weight history data available');
            const container = chartCanvas.parentElement;
            if (container) {
                container.innerHTML = `
                    <div class="alert alert-info text-center">
                        <i class="fas fa-scale me-2"></i>
                        No weight history available. Start logging your weight to see your progress!
                    </div>
                `;
            }
            return;
        }

        // Sort data by timestamp
        const sortedData = data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        // Format dates and weights for display
        const formattedData = sortedData.map(log => ({
            x: new Date(log.timestamp).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            }),
            y: parseFloat(log.weight)
        }));

        // Calculate y-axis range with padding
        const weights = formattedData.map(d => d.y);
        const minWeight = Math.min(...weights);
        const maxWeight = Math.max(...weights);
        const range = maxWeight - minWeight;
        const padding = Math.max(range * 0.1, 1); // At least 1 unit padding

        // Destroy existing chart if it exists
        if (weightChart instanceof Chart) {
            weightChart.destroy();
        }

        // Set canvas dimensions before creating new chart
        chartCanvas.style.height = '400px';
        chartCanvas.style.width = '100%';

        // Create new chart
        weightChart = new Chart(chartCanvas, {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Weight (lbs)',
                    data: formattedData,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Weight: ${context.raw.y.toFixed(1)} lbs`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        min: Math.max(0, minWeight - padding),
                        max: maxWeight + padding,
                        title: {
                            display: true,
                            text: 'Weight (lbs)'
                        },
                        ticks: {
                            callback: function(value) {
                                return value.toFixed(1) + ' lbs';
                            }
                        }
                    },
                    x: {
                        type: 'category',
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    }
                }
            }
        });

        console.log('Weight chart initialized successfully');
    } catch (error) {
        console.error('Error initializing weight chart:', error);
        const container = chartCanvas.parentElement;
        if (container) {
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error initializing weight chart: ${error.message}
                </div>
            `;
        }
    }
}

// Update displays function
function updateDisplays(data) {
    console.log('Updating displays with data:', data);

    // Update water displays
    const waterDisplays = document.querySelectorAll('#daily-water');
    waterDisplays.forEach(display => {
        if (display) {
            display.textContent = data.totalWater.toFixed(1);
        }
    });

    // Update water goal displays
    const waterGoalElements = document.querySelectorAll('#water-goal');
    waterGoalElements.forEach(element => {
        if (element && data.waterGoal) {
            element.textContent = data.waterGoal.toFixed(1);
        }
    });

    // Update calorie displays
    const calorieDisplays = document.querySelectorAll('#daily-calories');
    calorieDisplays.forEach(display => {
        if (display) {
            display.textContent = Math.round(data.totalCalories);
        }
    });

    // Update calorie goal displays
    const calorieGoalElements = document.querySelectorAll('#calorie-goal');
    calorieGoalElements.forEach(element => {
        if (element && data.calorieGoal) {
            element.textContent = Math.round(data.calorieGoal);
        }
    });

    // Update food log entries if they exist
    if (data.foodLogs) {
        updateFoodLogEntries(data.foodLogs);
    }

    // Initialize or update weight chart if weight history is available
    if (data.weightHistory && data.weightHistory.length > 0) {
        initializeWeightChart(data.weightHistory);
    }

    // Update progress bars
    updateProgress();
}

function updateProgress() {
    try {
        console.log('Updating progress bars...');

        // Update water progress
        const waterConsumed = parseFloat(document.getElementById('daily-water').textContent) || 0;
        const waterGoal = parseFloat(document.getElementById('water-goal').textContent) || 0;
        const waterPercentage = waterGoal > 0 ? Math.min(100, (waterConsumed / waterGoal) * 100) : 0;

        const waterProgressBar = document.getElementById('water-progress');
        if (waterProgressBar) {
            waterProgressBar.style.width = waterPercentage + '%';
            waterProgressBar.setAttribute('aria-valuenow', waterPercentage);
        }

        console.log('Progress bars updated successfully');
    } catch (error) {
        console.error('Error updating progress bars:', error);
    }
}

async function updateDailySummary() {
    try {
        console.log('Fetching daily summary...');
        const response = await fetch('/api/daily-summary');
        if (!response.ok) {
            throw new Error('Failed to fetch daily summary');
        }
        const data = await response.json();
        console.log('Daily summary response:', data);
        updateDisplays(data);
    } catch (error) {
        console.error('Error updating daily summary:', error);
    }
}

function checkDayChange() {
    updateDailySummary();
}

async function searchFood() {
    const query = document.getElementById('food-search').value.trim();
    if (!query) return;

    const searchResults = document.getElementById('search-results');
    searchResults.innerHTML = `
        <div class="text-center my-3">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Searching...</span>
            </div>
            <p class="mt-2">Searching for "${query}"...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/search-food?query=${encodeURIComponent(query)}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Food search response:', data);

        if (data.status === 'success' && data.results && data.results.length > 0) {
            searchResults.innerHTML = '';
            data.results.forEach(food => {
                const foodItem = document.createElement('button');
                foodItem.className = 'list-group-item list-group-item-action';
                foodItem.type = 'button';
                foodItem.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${food.name}</h6>
                        <small>${Math.round(food.nutrients.calories)} cal</small>
                    </div>
                    <p class="mb-1">
                        Protein: ${Math.round(food.nutrients.protein)}g | 
                        Carbs: ${Math.round(food.nutrients.carbs)}g | 
                        Fat: ${Math.round(food.nutrients.fat)}g
                    </p>
                    <small>${food.category}</small>
                `;
                foodItem.addEventListener('click', () => handleFoodSelection(food));
                searchResults.appendChild(foodItem);
            });
        } else {
            searchResults.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle me-2"></i>
                    No results found for "${query}"
                </div>
            `;
        }
    } catch (error) {
        console.error('Error searching food:', error);
        searchResults.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${error.message || 'Error searching for food. Please try again.'}
            </div>
        `;
    }
}

function handleFoodSelection(food) {
    // Fill in the form with selected food data
    document.getElementById('food-name').value = food.name;
    document.getElementById('serving-size').value = 1;
    // Always keep unit as 'serving' regardless of what comes from the API
    document.getElementById('unit').value = 'serving';

    // Store nutrient information in hidden fields or data attributes
    const form = document.getElementById('food-log-form');
    form.dataset.calories = food.nutrients.calories;
    form.dataset.protein = food.nutrients.protein;
    form.dataset.carbs = food.nutrients.carbs;
    form.dataset.fat = food.nutrients.fat;
}

function updateWellnessQuote(quoteData) {
    if (!quoteData) return;

    const quoteText = document.getElementById('quote-text');
    const quoteAuthor = document.getElementById('quote-author');

    if (quoteText && quoteData.text) {
        quoteText.textContent = quoteData.text;
    }

    if (quoteAuthor && quoteData.author) {
        quoteAuthor.textContent = quoteData.author;
    }
}

async function updateWeightHistory() {
    const chartContainer = document.querySelector('.weight-chart-container');

    // Show loading state
    chartContainer.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading weight history...</p>
        </div>
    `;

    try {
        const response = await fetch('/api/weight-history');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.status === 'success' && data.data) {
            // Restore the canvas element
            chartContainer.innerHTML = '<canvas id="weightChart" style="height: 300px; width: 100%;"></canvas>';

            // Initialize chart with the new data
            await initializeWeightChart(data.data);

            // Display milestone message if available
            const milestoneDiv = document.getElementById('milestone-message');
            if (data.summary && data.summary.milestone_message) {
                milestoneDiv.textContent = data.summary.milestone_message;
                milestoneDiv.style.display = 'block';
            }
        } else {
            throw new Error(data.message || 'Failed to load weight history');
        }
    } catch (error) {
        console.error('Error fetching weight history:', error);
        chartContainer.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Error loading weight history: ${error.message}
            </div>
        `;
    }
}

function updateFoodLogEntries(logs) {
    const foodLogEntries = document.getElementById('food-log-entries');
    if (!foodLogEntries) return;

    foodLogEntries.innerHTML = '';

    if (!logs || logs.length === 0) {
        foodLogEntries.innerHTML = '<p class="text-center text-muted my-3">No food logs for today</p>';
        return;
    }

    logs.forEach(log => {
        const entry = document.createElement('div');
        entry.className = 'list-group-item';
        entry.innerHTML = `
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1">${log.foodName}</h6>
                <small>${new Date(log.timestamp).toLocaleTimeString()}</small>
            </div>
            <p class="mb-1">
                ${log.servingSize} ${log.unit} - ${log.mealType}
                <br>
                Calories: ${Math.round(log.calories)} | 
                Protein: ${Math.round(log.protein)}g | 
                Carbs: ${Math.round(log.carbs)}g | 
                Fat: ${Math.round(log.fat)}g
            </p>
            <small>
                Emotional State: ${log.emotionalState || 'Not specified'} | 
                Satisfaction: ${log.satisfactionLevel}/5
                ${log.notes ? '<br>Notes: ' + log.notes : ''}
            </small>
        `;
        foodLogEntries.appendChild(entry);
    });
}

async function handleWeightSubmit(e) {
    e.preventDefault();
    const weight = parseFloat(document.getElementById('log-weight').value);
    const notes = document.getElementById('weight-notes').value;
    const errorDiv = document.getElementById('weight-error');
    const milestoneDiv = document.getElementById('milestone-message');

    // Input validation
    if (!weight || weight <= 0 || isNaN(weight)) {
        errorDiv.textContent = 'Please enter a valid weight';
        errorDiv.style.display = 'block';
        return;
    }

    // Hide previous error messages
    errorDiv.style.display = 'none';
    milestoneDiv.style.display = 'none';

    try {
        console.log('Submitting weight log:', { weight, notes });
        const response = await fetch('/api/log-weight', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ weight, notes })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Weight log response:', data);

        if (data.status === 'success') {
            // Clear form
            document.getElementById('log-weight').value = '';
            document.getElementById('weight-notes').value = '';

            // Update weight history
            await updateWeightHistory();

            // Show milestone message if available
            if (data.milestone_message) {
                milestoneDiv.textContent = data.milestone_message;
                milestoneDiv.style.display = 'block';
            }
        } else {
            throw new Error(data.message || 'Failed to log weight');
        }
    } catch (error) {
        console.error('Error logging weight:', error);
        errorDiv.textContent = error.message || 'Error logging weight';
        errorDiv.style.display = 'block';
    }
}

async function handleFoodLogSubmit(event) {
    event.preventDefault();

    const form = document.getElementById('food-log-form');
    if (!form) return;

    const servingSize = parseFloat(document.getElementById('serving-size').value) || 1;

    // Validate required fields
    const foodName = document.getElementById('food-name').value;
    if (!foodName) {
        alert('Please select a food item first');
        return;
    }

    const formData = {
        foodName: foodName,
        servingSize: servingSize,
        unit: document.getElementById('unit').value || 'serving',
        mealType: document.getElementById('meal-type').value,
        emotionalState: document.getElementById('emotional-state').value,
        satisfactionLevel: document.getElementById('satisfaction-level').value,
        hungerBefore: document.getElementById('hunger-before').value,
        fullnessAfter: document.getElementById('fullness-after').value,
        notes: document.getElementById('notes').value,
        // Add nutrient data from the form dataset
        calories: (parseFloat(form.dataset.calories) || 0) * servingSize,
        protein: (parseFloat(form.dataset.protein) || 0) * servingSize,
        carbs: (parseFloat(form.dataset.carbs) || 0) * servingSize,
        fat: (parseFloat(form.dataset.fat) || 0) * servingSize
    };

    try {
        console.log('Submitting food log:', formData);
        const response = await fetch('/api/log-food', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Food log response:', data);

        if (data.status === 'success') {
            // Reset form
            form.reset();
            // Clear any stored nutrient data
            form.dataset.calories = '';
            form.dataset.protein = '';
            form.dataset.carbs = '';
            form.dataset.fat = '';
            // Update displays immediately
            await updateDailySummary();
            // Switch to food log history tab if it exists
            const historyTab = document.getElementById('history-tab');
            if (historyTab) {
                historyTab.click();
            }
        } else {
            throw new Error(data.message || 'Failed to log food');
        }
    } catch (error) {
        console.error('Error logging food:', error);
        alert('Error logging food: ' + (error.message || 'Please try again'));
    }
}