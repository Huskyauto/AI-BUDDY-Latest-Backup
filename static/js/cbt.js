document.addEventListener('DOMContentLoaded', () => {
    // Initialize all accordions
    const accordionItems = document.querySelectorAll('.accordion-item');

    // Add click handlers to all accordion buttons
    accordionItems.forEach(item => {
        const button = item.querySelector('.accordion-button');
        const content = item.querySelector('.accordion-collapse');

        if (button && content) {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const isExpanded = button.getAttribute('aria-expanded') === 'true';

                // Toggle current item
                button.setAttribute('aria-expanded', !isExpanded);
                content.classList.toggle('show');

                // Optional: Close other items when opening this one
                if (!isExpanded) {
                    accordionItems.forEach(otherItem => {
                        if (otherItem !== item) {
                            const otherButton = otherItem.querySelector('.accordion-button');
                            const otherContent = otherItem.querySelector('.accordion-collapse');
                            if (otherButton && otherContent) {
                                otherButton.setAttribute('aria-expanded', 'false');
                                otherContent.classList.remove('show');
                            }
                        }
                    });
                }
            });
        }
    });

    // Load static content for sections
    loadSectionContent('behavioral', `
        <ul class="list-unstyled">
            <li class="mb-2">• Observed patterns in eating habits during stressful periods</li>
            <li class="mb-2">• Identified emotional triggers leading to mindless eating</li>
            <li class="mb-2">• Notice tendency to skip meals when feeling overwhelmed</li>
            <li class="mb-2">• Recognize comfort food patterns during anxiety</li>
        </ul>
    `);

    loadSectionContent('exercises', `
        <ul class="list-unstyled">
            <li class="mb-2">• Thought Record: Document automatic thoughts before meals</li>
            <li class="mb-2">• Mindfulness Exercise: 5-minute breathing before eating</li>
            <li class="mb-2">• Emotion Scale: Rate hunger vs emotional needs</li>
            <li class="mb-2">• Activity Planning: Schedule regular meal times</li>
        </ul>
    `);

    loadSectionContent('mindful', `
        <ul class="list-unstyled">
            <li class="mb-2">• Practice the STOP technique before meals</li>
            <li class="mb-2">• Use the 5 senses approach while eating</li>
            <li class="mb-2">• Set designated eating spaces and times</li>
            <li class="mb-2">• Remove distractions during meals</li>
        </ul>
    `);

    loadSectionContent('reframing', `
        <ul class="list-unstyled">
            <li class="mb-2">• "I always overeat" → "I'm learning to listen to my body's signals"</li>
            <li class="mb-2">• "I have no control" → "I can make conscious choices about my eating"</li>
            <li class="mb-2">• "I'm a failure" → "I'm making progress and learning from setbacks"</li>
        </ul>
    `);

    loadSectionContent('nextSteps', `
        <ul class="list-unstyled">
            <li class="mb-2">• Continue monitoring emotional states before meals</li>
            <li class="mb-2">• Practice one mindfulness exercise daily</li>
            <li class="mb-2">• Use thought records for challenging situations</li>
            <li class="mb-2">• Schedule follow-up session to review progress</li>
        </ul>
    `);
});

function loadSectionContent(sectionId, content) {
    const section = document.querySelector(`#${sectionId} .accordion-body`);
    if (section) {
        section.innerHTML = content;
    }
}