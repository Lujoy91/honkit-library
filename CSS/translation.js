(function () {
    function initTranslationMode() {
        const containers = document.querySelectorAll('.translation-container');

        if (!containers.length) {
            return;
        }

        containers.forEach(function (container) {
            if (container.dataset.translationReady === 'true') {
                return;
            }

            container.dataset.translationReady = 'true';

            const buttons = document.createElement('div');
            buttons.className = 'translation-buttons';

            const modes = [
                { name: '原文', className: 'show-original' },
                { name: '翻譯', className: 'show-translated' },
                { name: '左右對照', className: 'show-both' }
            ];

            modes.forEach(function (mode, index) {
                const button = document.createElement('button');

                button.type = 'button';
                button.textContent = mode.name;
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

                    container.classList.add(mode.className);

                    buttons
                        .querySelectorAll('.translation-button')
                        .forEach(function (btn) {
                            btn.classList.remove('active');
                        });

                    button.classList.add('active');
                });

                buttons.appendChild(button);
            });

            container.parentNode.insertBefore(buttons, container);
            container.classList.add('show-both');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTranslationMode);
    } else {
        initTranslationMode();
    }
})();