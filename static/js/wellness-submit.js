// Global function for mobile compatibility
window.handleMobileSubmit = async function(event) {
    console.log('Mobile submit function called!');
    event.preventDefault();
    event.stopPropagation();
    
    const form = document.getElementById('wellness-form');
    if (form) {
        await handleWellnessSubmit(form);
    }
    return false;
};

// Wellness check-in submission - using same method as working water logging
document.addEventListener('DOMContentLoaded', function() {
    console.log('Wellness submit script loaded');
    const wellnessForm = document.getElementById('wellness-form');
    console.log('Found wellness form:', wellnessForm);
    
    if (wellnessForm) {
        console.log('Adding submit listener to wellness form');
        
        // Add direct onclick handler for mobile compatibility
        const submitBtn = wellnessForm.querySelector('button[type="submit"]');
        console.log('Found submit button:', submitBtn);
        if (submitBtn) {
            console.log('Adding click listener to submit button');
            console.log('Button text:', submitBtn.textContent);
            console.log('Button type:', submitBtn.type);
            
            // Set direct onclick attribute for maximum mobile compatibility
            submitBtn.onclick = async function(e) {
                console.log('Submit button clicked via onclick!');
                e.preventDefault();
                e.stopPropagation();
                await handleWellnessSubmit(wellnessForm);
                return false;
            };
            
            // Also add addEventListener as backup
            submitBtn.addEventListener('click', async function(e) {
                console.log('Submit button clicked via addEventListener!');
                e.preventDefault();
                e.stopPropagation();
            });
        }
        
        wellnessForm.addEventListener('submit', async function(e) {
            console.log('Wellness form submit triggered!');
            e.preventDefault();
            await handleWellnessSubmit(wellnessForm);
        });
    }
});

async function handleWellnessSubmit(wellnessForm) {
    const submitBtn = wellnessForm.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';
    }
    
    try {
        // Collect form data exactly like working water logging
        const formData = new FormData(wellnessForm);
        const data = {
            energy_level: formData.get('energy_level') || '5',
            physical_comfort: formData.get('physical_comfort') || '5',
            sleep_quality: formData.get('sleep_quality') || '5',
            breathing_quality: formData.get('breathing_quality') || '5',
            physical_tension: formData.get('physical_tension') || '5',
            stress_level: formData.get('stress_level') || '5',
            mood: formData.get('mood') || 'neutral',
            focus_level: formData.get('focus_level') || '5',
            exercise_minutes: formData.get('exercise_minutes') || '0',
            water_glasses: formData.get('water_glasses') || '0',
            weather_condition: formData.get('weather_condition') || '',
            location_type: formData.get('location_type') || '',
            notes: formData.get('notes') || ''
        };
        
        console.log('Submitting wellness data:', data);
        
        // Use JSON submission like successful water logging
        const response = await fetch('/self-care/wellness-check-in-api', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        
        console.log('Response status:', response.status);
        if (response.ok) {
            const result = await response.json();
            console.log('Success response:', result);
            alert('✅ Wellness check-in saved successfully!');
            window.location.reload();
        } else {
            console.log('Error response status:', response.status);
            const error = await response.text();
            console.log('Error response:', error);
            alert('❌ Error saving check-in: ' + error);
        }
        
    } catch (error) {
        console.error('Error:', error);
        alert('❌ Network error. Please try again.');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Save Check-In';
        }
    }
}