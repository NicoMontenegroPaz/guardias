/**
 * Controlador Principal de la Aplicación (SPA).
 * Gestiona la navegación entre pestañas, diálogos modales, notificaciones toast y el generador de guardias.
 */

class AppController {
    constructor() {
        this.activeTab = 'cuadrante';
        this.init();
    }

    init() {
        this.bindNavigation();
        this.bindModals();
        this.bindGenerator();
        this.initializeApp();
    }

    bindNavigation() {
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const targetTab = tab.dataset.tab;
                this.switchTab(targetTab);
            });
        });
    }

    switchTab(tabId) {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        const targetNav = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
        const targetContent = document.getElementById(`tab-${tabId}`);

        if (targetNav && targetContent) {
            targetNav.classList.add('active');
            targetContent.classList.add('active');
            this.activeTab = tabId;

            // Cargar datos específicos al cambiar de pestaña
            if (tabId === 'cuadrante' && window.scheduleManager) {
                window.scheduleManager.loadAndRender();
            } else if (tabId === 'personal' && window.personnelManager) {
                window.personnelManager.loadPersonnel();
            } else if (tabId === 'puestos' && window.positionsManager) {
                window.positionsManager.loadPositionsAndTemplate();
            } else if (tabId === 'balance' && window.statsManager) {
                window.statsManager.loadAndRenderStats();
            } else if (tabId === 'feriados' && window.holidaysManager) {
                window.holidaysManager.loadHolidays();
            }
        }
    }

    bindModals() {
        // Cerrar modal al hacer clic en botones de cierre
        document.querySelectorAll('[data-close]').forEach(btn => {
            btn.addEventListener('click', () => {
                const modalId = btn.dataset.close;
                this.closeModal(modalId);
            });
        });

        // Cerrar modal al hacer clic en el fondo oscuro
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    this.closeModal(overlay.id);
                }
            });
        });

        // Cerrar con tecla Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal-overlay.active').forEach(modal => {
                    this.closeModal(modal.id);
                });
            }
        });
    }

    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
        }
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        if (type === 'error') icon = '❌';
        if (type === 'warning') icon = '⚠️';

        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    bindGenerator() {
        // Botón Header: Generar Guardia
        document.getElementById('btn-open-generator')?.addEventListener('click', () => {
            this.openGeneratorModal();
        });

        // Sincronizar fechas del generador según horizonte seleccionado
        const horizonRadios = document.querySelectorAll('input[name="gen-horizon"]');
        horizonRadios.forEach(radio => {
            radio.addEventListener('change', () => this.updateGeneratorDates());
        });

        const startDateInput = document.getElementById('gen-start-date');
        if (startDateInput) {
            startDateInput.addEventListener('change', () => this.updateGeneratorDates(false));
        }

        // Ejecutar Generación de Guardias
        document.getElementById('btn-run-generation')?.addEventListener('click', async (e) => {
            e.preventDefault();
            await this.runGeneration();
        });

        // Botón Header: Eliminar Guardias
        document.getElementById('btn-open-clear')?.addEventListener('click', () => {
            this.openClearModal();
        });

        // Ejecutar Eliminación
        document.getElementById('btn-run-clear')?.addEventListener('click', async (e) => {
            e.preventDefault();
            await this.runClear();
        });
    }

    openClearModal() {
        const today = new Date();
        const startInput = document.getElementById('clear-start-date');
        const endInput = document.getElementById('clear-end-date');
        
        if (window.scheduleManager && window.scheduleManager.startDate) {
            startInput.value = window.scheduleManager.startDate;
            const endDate = new Date(startInput.value + 'T00:00:00');
            endDate.setDate(endDate.getDate() + 30);
            endInput.value = endDate.toISOString().slice(0, 10);
        } else {
            startInput.value = today.toISOString().slice(0, 10);
            endInput.value = today.toISOString().slice(0, 10);
        }
        
        this.openModal('modal-clear');
    }

    async runClear() {
        const startInput = document.getElementById('clear-start-date').value;
        const endInput = document.getElementById('clear-end-date').value;

        if (!startInput || !endInput) {
            this.showToast('Por favor selecciona las fechas de inicio y fin', 'error');
            return;
        }

        if (confirm(`¿Estás seguro de que deseas eliminar todas las guardias generadas desde ${startInput} hasta ${endInput}?`)) {
            try {
                const result = await window.api.clearScheduleRange(startInput, endInput);
                if (result.success) {
                    this.closeModal('modal-clear');
                    this.showToast('Guardias eliminadas correctamente.', 'success');
                    if (window.scheduleManager) {
                        window.scheduleManager.loadAndRender();
                    }
                } else {
                    this.showToast(`Error: ${result.error}`, 'error');
                }
            } catch (err) {
                this.showToast(`Error: ${err.message}`, 'error');
            }
        }
    }

    openGeneratorModal() {
        const today = new Date();
        const startInput = document.getElementById('gen-start-date');
        
        // Si hay una fecha seleccionada en el cuadrante, usarla como base
        if (window.scheduleManager && window.scheduleManager.startDate) {
            startInput.value = window.scheduleManager.startDate;
        } else {
            startInput.value = today.toISOString().slice(0, 10);
        }

        this.updateGeneratorDates(true);
        this.openModal('modal-generator');
    }

    async updateGeneratorDates(resetToStart = true) {
        const startInput = document.getElementById('gen-start-date');
        const endInput = document.getElementById('gen-end-date');
        const horizonRadio = document.querySelector('input[name="gen-horizon"]:checked');

        if (!startInput.value) return;

        const startDate = new Date(startInput.value + 'T00:00:00');
        const horizon = horizonRadio ? horizonRadio.value : '7';

        let endDate = new Date(startDate);

        if (horizon === 'month') {
            // Último día del mes de la fecha de inicio
            endDate = new Date(startDate.getFullYear(), startDate.getMonth() + 1, 0);
        } else {
            const days = parseInt(horizon);
            endDate.setDate(startDate.getDate() + days - 1);
        }

        endInput.value = endDate.toISOString().slice(0, 10);

        // Actualizar vista previa
        const daysDiff = Math.round((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;
        document.getElementById('preview-days-count').textContent = `${daysDiff} días`;

        if (window.personnelManager && window.personnelManager.personnelList) {
            const activeCount = window.personnelManager.personnelList.filter(p => p.is_active).length;
            document.getElementById('preview-active-personnel').textContent = `${activeCount} integrantes`;
        }

        // Feriados en el rango
        try {
            const holidays = await window.api.getHolidays(startDate.getFullYear());
            const count = holidays.filter(h => h.date >= startInput.value && h.date <= endInput.value).length;
            document.getElementById('preview-holidays-count').textContent = count;
        } catch (e) {
            // Silencioso
        }
    }

    async runGeneration() {
        const startInput = document.getElementById('gen-start-date');
        const endInput = document.getElementById('gen-end-date');
        const preserveManual = document.getElementById('gen-preserve-manual')?.checked ?? true;

        const startDate = startInput.value;
        const endDate = endInput.value;

        if (!startDate || !endDate) {
            this.showToast('Por favor selecciona las fechas de inicio y fin', 'error');
            return;
        }

        const runBtn = document.getElementById('btn-run-generation');
        runBtn.disabled = true;
        runBtn.innerHTML = '<span>Generando guardias y balanceando...</span>';

        try {
            const result = await window.api.generateSchedule(startDate, endDate, !preserveManual);
            
            if (result.success) {
                this.closeModal('modal-generator');
                this.showToast(`¡Guardia generada con éxito! Se planificaron ${result.assignments_count} puestos para ${result.total_days} días.`, 'success');
                
                if (result.unfilled_slots && result.unfilled_slots.length > 0) {
                    this.showToast(`Advertencia: ${result.unfilled_slots.length} puestos no pudieron ser cubiertos por falta de personal disponible.`, 'warning');
                }

                // Sincronizar cuadrante
                const monthPicker = document.getElementById('cuadrante-month-picker');
                if (monthPicker) monthPicker.value = startDate.substring(0, 7);

                if (window.scheduleManager) {
                    window.scheduleManager.calculateDateRange();
                    window.scheduleManager.loadAndRender();
                }

                if (window.personnelManager) {
                    window.personnelManager.loadPersonnel(startDate.substring(0, 7));
                }

                if (window.statsManager) {
                    window.statsManager.loadAndRenderStats();
                }

                this.switchTab('cuadrante');
            } else {
                this.showToast(`Error al generar guardias: ${result.error}`, 'error');
            }
        } catch (err) {
            this.showToast(`Error en la generación: ${err.message}`, 'error');
        } finally {
            runBtn.disabled = false;
            runBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                <span>Generar y Balancear Turnos</span>
            `;
        }
    }

    async initializeApp() {
        // Cargar datos iniciales
        if (window.personnelManager) await window.personnelManager.loadPersonnel();
        if (window.positionsManager) await window.positionsManager.loadPositionsAndTemplate();
        if (window.scheduleManager) await window.scheduleManager.loadAndRender();
        if (window.holidaysManager) await window.holidaysManager.loadHolidays();
        if (window.statsManager) await window.statsManager.loadAndRenderStats();

        try {
            const config = await window.api.getConfig();
            const weekStartSelect = document.getElementById('select-week-start');
            if (weekStartSelect && config && config.week_start_day !== undefined) {
                weekStartSelect.value = config.week_start_day.toString();
            }
            if (weekStartSelect) {
                weekStartSelect.addEventListener('change', async (e) => {
                    await window.api.setConfig(parseInt(e.target.value));
                    this.showToast('Día de inicio de semana actualizado. Regenera las guardias para aplicar cambios.', 'success');
                });
            }
        } catch (e) {
            console.error("No se pudo cargar la config:", e);
        }

        console.log("Sistema de Gestión y Generación de Guardias iniciado correctamente.");
    }
}

// Inicialización cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.app = new AppController();
});
