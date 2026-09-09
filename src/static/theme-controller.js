/**
 * =========================================================================
 *  THEME CONTROLLER — GASTOS RACCOON
 *  Controlador global para modo claro/oscuro con View Transitions
 * =========================================================================
 */

(function() {
    'use strict';
    
    // Evitar doble inicialización
    if (window.ThemeController) return;

    class ThemeController {
        constructor() {
            this.currentTheme = localStorage.getItem('theme') || 'dark';
            this.applyTheme(this.currentTheme, false);
            this.bindEvents();
        }

        applyTheme(theme, animate = false, event = null) {
            const isDark = theme === 'dark';
            const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

            const changeDOM = () => {
                document.documentElement.className = theme;
                document.documentElement.setAttribute('data-theme', theme);
                localStorage.setItem('theme', theme);
                this.currentTheme = theme;
                
                // Disparar evento custom para gráficas, canvas, etc.
                window.dispatchEvent(new CustomEvent('themechange', {
                    detail: { theme: theme, isDark: isDark }
                }));

                // Cambiar el icono del botón (asumiendo lucide-icons)
                const themeBtns = document.querySelectorAll('#theme-btn i');
                themeBtns.forEach(icon => {
                    if (isDark) {
                        icon.setAttribute('data-lucide', 'moon');
                    } else {
                        icon.setAttribute('data-lucide', 'sun');
                    }
                });
                
                if (window.lucide && window.lucide.createIcons) {
                    window.lucide.createIcons();
                }
            };

            // Transición animada (radial desde el click)
            if (animate && !reduceMotion && document.startViewTransition && event) {
                const x = event.clientX;
                const y = event.clientY;
                const endRadius = Math.hypot(
                    Math.max(x, innerWidth - x),
                    Math.max(y, innerHeight - y)
                );

                const transition = document.startViewTransition(() => {
                    changeDOM();
                });

                transition.ready.then(() => {
                    const clipPath = [
                        `circle(0px at ${x}px ${y}px)`,
                        `circle(${endRadius}px at ${x}px ${y}px)`,
                    ];
                    
                    document.documentElement.animate(
                        {
                            clipPath: isDark ? [...clipPath].reverse() : clipPath,
                        },
                        {
                            duration: 260,
                            easing: "cubic-bezier(.22, 1, .36, 1)",
                            pseudoElement: isDark ? "::view-transition-old(root)" : "::view-transition-new(root)",
                        }
                    );
                });
            } else {
                changeDOM();
            }
        }

        toggle(event) {
            const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
            this.applyTheme(newTheme, true, event);
        }

        bindEvents() {
            // Reemplazar global toggleTheme
            window.toggleTheme = (event) => {
                const ev = event || window.event;
                this.toggle(ev);
            };
        }
    }

    window.ThemeController = new ThemeController();
})();
