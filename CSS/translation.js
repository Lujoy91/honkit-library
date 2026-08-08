(function () {
    function initTranslationMode() {
        const article = document.querySelector('.page-inner');

        if (!article) {
            return;
        }

        const headings = article.querySelectorAll('h2');

        let originalHeading = null;
        let translatedHeading = null;

        headings.forEach(function (heading) {
            const text = heading.textContent.trim();

            if (text.includes('原文')) {
                originalHeading = heading;
            }

            if (text.includes('翻譯')) {
                translatedHeading = heading;
            }
        });

        if (!originalHeading || !translatedHeading) {
            return;
        }

        if (article.querySelector('.translation-container')) {
            return;
        }

        const originalBox = document.createElement('div');
        originalBox.className = 'translation-original';

        const translatedBox = document.createElement('div');
        translatedBox.className = 'translation-translated';

        let node = originalHeading;

        while (node && node !== translatedHeading) {
            const next = node.nextElementSibling;

            originalBox.appendChild(node);

            if (next === translatedHeading) {
                break;
            }

            if (next) {
                originalBox.appendChild(next);
            }

            node = next;
        }

        node = translatedHeading;

        while (node) {
            const next = node.nextElementSibling;

            translatedBox.appendChild(node);

            node = next;
        }

        const container = document.createElement('div');
        container.className = 'translation-container show-both';

        container.appendChild(originalBox);
        container.appendChild(translatedBox);

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

                buttons.querySelectorAll('.translation-button').forEach(function (item) {
                    item.classList.remove('active');
                });

                button.classList.add('active');
            });

            buttons.appendChild(button);
        });

        originalHeading.parentNode.insertBefore(buttons, originalHeading);
        originalHeading.parentNode.insertBefore(container, buttons.nextSibling);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTranslationMode);
    } else {
        initTranslationMode();
    }
})();