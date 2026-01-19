// Create notification sound with Tone.js
function createNotificationSound() {
    try {
        // Create synth and effects
        const synth = new Tone.Synth({
            oscillator: { type: 'sine' },
            envelope: { attack: 0.01, decay: 0.1, sustain: 0.1, release: 0.5 }
        }).toDestination();
        
        // Create a simple notification sound
        const playNotification = () => {
            // Make sure Tone.js is started
            Tone.start();
            
            // Play a sequence of tones
            synth.triggerAttackRelease("C5", "16n");
            setTimeout(() => synth.triggerAttackRelease("E5", "16n"), 150);
            setTimeout(() => synth.triggerAttackRelease("G5", "16n"), 300);
            
            return true;
        };
        
        return playNotification;
    } catch (error) {
        console.error('Failed to create notification sound:', error);
        return () => false;
    }
}
