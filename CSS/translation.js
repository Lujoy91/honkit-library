(function () {
    function initTranslationMode() {
        const headings = document.querySelectorAll('h2');

        let original = null;
        let translated = null;

        headings.forEach(function (heading) {
            const text = heading.textContent.trim();

            if (text.includes('原文')) {
                original = heading;
            }

            if (text.includes('翻譯')) {
                translated = heading;
            }
        });

        if (!original || !translated) {
            return;
        }

        if (document.querySelector('.translation-buttons')) {
            return;
        }

        const originalContent = document.createElement('div');
        originalContent.className = 'translation-original';

        const translatedContent = document.createElement('div');
        translatedContent.className = 'translation-translated';

        let current = original.nextElementSibling;

        while (current && current !== translated) {
            const next = current.nextElementSibling;
            originalContent.appendChild(current);
            current = next;
        }

        current = translated.nextElementSibling;

        while (current) {
            const next = current.nextElementSibling;
            translatedContent.appendChild(current);
            current = next;
        }

        original.remove();
        translated.remove();

        const container = document.createElement('div');
        container.className = 'translation-container show-both';

        container.appendChild(originalContent);
        container.appendChild(translatedContent);

        const buttons = document.createElement('div');
        buttons.className = 'translation-buttons';

        const modes = [
            ['原文', 'show-original'],
            ['翻譯', 'show-translated'],
            ['左右對照', 'show-both']
        ];

        modes.forEach(function (mode, index) {
            const button = document.createElement('button');

            button.type = 'button';
            button.textContent = mode[0];
            button.className = 'translation-button';

            if (index === 2) {
                button.classList.add('active');
            }

            button.addEventListener('click', function () {
                container.classList.remove(
                    'show-original',
                    'show-translated',
                    'show-both'
                );

                container.classList.add(mode[1]);

                buttons
                    .querySelectorAll('.translation-button')
                    .forEach(function (item) {
                        item.classList.remove('active');
                    });

                button.classList.add('active');
            });

            buttons.appendChild(button);
        });

        originalContent.parentNode.insertBefore(buttons, originalContent);
        originalContent.parentNode.insertBefore(container, buttons.nextSibling);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTranslationMode);
    } else {
        initTranslationMode();
    }
})();