/**
 * Módulo de Visualización y Gestión de Feriados Nacionales de Argentina e Institucionales.
 */

class HolidaysManager {
    constructor() {
        this.currentYear = new Date().getFullYear();
        this.holidaysList = [];

        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        const yearSelect = document.getElementById('holiday-year-select');
        if (yearSelect) {
            yearSelect.value = String(this.currentYear);
            yearSelect.addEventListener('change', (e) => {
                this.currentYear = parseInt(e.target.value);
                this.loadHolidays();
            });
        }

        document.getElementById('btn-add-custom-holiday')?.addEventListener('click', () => {
            const dateInput = document.getElementById('holiday-date');
            const nameInput = document.getElementById('holiday-name');
            if (dateInput) dateInput.value = `${this.currentYear}-01-01`;
            if (nameInput) nameInput.value = '';
            window.app.openModal('modal-holiday');
        });

        document.getElementById('btn-save-custom-holiday')?.addEventListener('click', () => this.saveCustomHoliday());
    }

    async loadHolidays() {
        const tbody = document.getElementById('holidays-table-body');
        if (!tbody) return;

        tbody.innerHTML = '<tr><td colspan="5" class="text-center">Cargando feriados de Argentina...</td></tr>';

        try {
            this.holidaysList = await window.api.getHolidays(this.currentYear);
            this.renderTable();
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="color:#ef4444;">Error: ${err.message}</td></tr>`;
        }
    }

    renderTable() {
        const tbody = document.getElementById('holidays-table-body');
        if (!tbody) return;

        if (this.holidaysList.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No se registraron feriados para este año.</td></tr>';
            return;
        }

        const weekdayNames = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

        let html = '';
        for (const h of this.holidaysList) {
            const dt = new Date(h.date + 'T00:00:00');
            const weekdayName = weekdayNames[dt.getDay() === 0 ? 6 : dt.getDay() - 1];
            const [y, m, d] = h.date.split('-');

            html += `
                <tr>
                    <td><strong>${d}/${m}/${y}</strong></td>
                    <td><span style="color:#94a3b8;">${weekdayName}</span></td>
                    <td>
                        <span style="font-weight:600; color:#ffffff;">${h.name}</span>
                    </td>
                    <td>
                        <span class="badge-tag ${h.is_custom ? 'badge-role' : 'badge-special'}" style="background:rgba(245, 158, 11, 0.15); color:#f59e0b;">
                            ${h.is_custom ? 'Institucional / Personalizado' : 'Feriado Nacional (Argentina)'}
                        </span>
                    </td>
                    <td class="text-right">
                        ${h.is_custom ? `
                            <button class="btn btn-sm btn-ghost btn-del-holiday" data-id="${h.id}" style="color:#ef4444;">🗑️</button>
                        ` : '<span style="font-size:0.75rem; color:#64748b;">Oficial</span>'}
                    </td>
                </tr>
            `;
        }

        tbody.innerHTML = html;

        tbody.querySelectorAll('.btn-del-holiday').forEach(btn => {
            btn.addEventListener('click', async () => {
                const hid = parseInt(btn.dataset.id);
                if (confirm('¿Eliminar este feriado institucional?')) {
                    await window.api.deleteCustomHoliday(hid);
                    window.app.showToast('Feriado eliminado', 'warning');
                    this.loadHolidays();
                    if (window.scheduleManager) window.scheduleManager.loadAndRender();
                }
            });
        });
    }

    async saveCustomHoliday() {
        const dateInput = document.getElementById('holiday-date');
        const nameInput = document.getElementById('holiday-name');

        const dateStr = dateInput.value;
        const name = nameInput.value.trim();

        if (!dateStr || !name) {
            window.app.showToast('Completa todos los campos obligatorios', 'error');
            return;
        }

        try {
            await window.api.saveCustomHoliday(dateStr, name);
            window.app.closeModal('modal-holiday');
            window.app.showToast('Feriado institucional guardado', 'success');
            await this.loadHolidays();
            if (window.scheduleManager) window.scheduleManager.loadAndRender();
        } catch (err) {
            window.app.showToast('Error al guardar feriado: ' + err.message, 'error');
        }
    }
}

// Instancia global
window.holidaysManager = new HolidaysManager();
