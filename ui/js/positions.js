/**
 * Módulo de Gestión de Puestos de Guardia y Plantilla de Dotación Semanal.
 * Permite agregar/quitar puestos (Semanales o Diarios) y configurar qué puestos se cubren en cada día de la semana.
 */

class PositionsManager {
    constructor() {
        this.positionsList = [];
        this.weeklyTemplate = {};

        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        document.getElementById('btn-add-position')?.addEventListener('click', () => this.openPositionModal());
        document.getElementById('btn-save-position')?.addEventListener('click', () => this.savePosition());
        document.getElementById('btn-save-weekly-template')?.addEventListener('click', () => this.saveWeeklyTemplate());
    }

    async loadPositionsAndTemplate() {
        try {
            this.positionsList = await window.api.getPositions();
            this.weeklyTemplate = await window.api.getWeeklyTemplate();
            this.renderPositionsList();
            this.renderWeeklyTemplate();
        } catch (err) {
            console.error('Error al cargar puestos y plantilla:', err);
        }
    }

    renderPositionsList() {
        const container = document.getElementById('positions-list-container');
        const countBadge = document.getElementById('positions-count-badge');
        if (!container) return;

        if (countBadge) {
            countBadge.textContent = `${this.positionsList.length} Puestos`;
        }

        if (this.positionsList.length === 0) {
            container.innerHTML = '<div style="color:#94a3b8; padding:10px;">No hay puestos de guardia configurados.</div>';
            return;
        }

        let html = '';
        for (const pos of this.positionsList) {
            const isWeekly = pos.is_weekly === 1;
            html += `
                <div class="position-item-card ${isWeekly ? 'position-card-weekly' : ''}">
                    <div class="position-item-info">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span class="position-item-name">#${pos.sort_order} — ${pos.name}</span>
                            ${isWeekly ? '<span class="badge-tag badge-weekly-tag">SEMANA (JUE - MIÉ)</span>' : '<span class="badge-tag badge-daily-tag">DIARIO</span>'}
                        </div>
                        <span class="position-item-req">Rol Requerido: <strong>${pos.required_role}</strong></span>
                    </div>
                    <div>
                        <button class="btn btn-sm btn-outline btn-edit-pos" data-id="${pos.id}">✏️</button>
                        <button class="btn btn-sm btn-ghost btn-delete-pos" data-id="${pos.id}" style="color:#ef4444;">🗑️</button>
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;

        container.querySelectorAll('.btn-edit-pos').forEach(btn => {
            btn.addEventListener('click', () => {
                const pid = parseInt(btn.dataset.id);
                const pos = this.positionsList.find(p => p.id === pid);
                if (pos) this.openPositionModal(pos);
            });
        });

        container.querySelectorAll('.btn-delete-pos').forEach(btn => {
            btn.addEventListener('click', async () => {
                const pid = parseInt(btn.dataset.id);
                const pos = this.positionsList.find(p => p.id === pid);
                if (pos && confirm(`¿Deseas eliminar el puesto "${pos.name}"?`)) {
                    await window.api.deletePosition(pid);
                    window.app.showToast('Puesto eliminado', 'warning');
                    this.loadPositionsAndTemplate();
                    if (window.scheduleManager) window.scheduleManager.loadAndRender();
                }
            });
        });
    }

    renderWeeklyTemplate() {
        const container = document.getElementById('weekly-template-container');
        if (!container) return;

        const dayNames = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

        let html = '<table class="weekly-template-table">';
        html += '<thead><tr><th>Puesto / Servicio</th>';
        for (const name of dayNames) {
            html += `<th>${name}</th>`;
        }
        html += '</tr></thead><tbody>';

        for (const pos of this.positionsList) {
            const isWeekly = pos.is_weekly === 1;
            html += `
                <tr class="${isWeekly ? 'row-weekly-pos' : ''}">
                    <td>
                        <strong>${pos.name}</strong> 
                        <small style="color:#38bdf8;">(${pos.required_role})</small>
                        ${isWeekly ? '<span class="badge-tag badge-weekly-tag" style="margin-left:6px;">SEMANA</span>' : ''}
                    </td>
            `;
            for (let d = 0; d < 7; d++) {
                const dayEntries = this.weeklyTemplate[d] || [];
                const entry = dayEntries.find(e => e.position_id === pos.id);
                const isChecked = entry ? entry.is_enabled === 1 : true;

                html += `
                    <td>
                        <input type="checkbox" class="cb-weekly-pos" data-day="${d}" data-pos-id="${pos.id}" ${isChecked ? 'checked' : ''}>
                    </td>
                `;
            }
            html += '</tr>';
        }

        html += '</tbody></table>';
        container.innerHTML = html;
    }

    async saveWeeklyTemplate() {
        const checkboxes = document.querySelectorAll('.cb-weekly-pos');
        const payload = [];

        checkboxes.forEach(cb => {
            payload.push({
                day_of_week: parseInt(cb.dataset.day),
                position_id: parseInt(cb.dataset.posId),
                is_enabled: cb.checked
            });
        });

        try {
            await window.api.updateWeeklyTemplate(payload);
            window.app.showToast('Plantilla de dotación semanal guardada con éxito', 'success');
            await this.loadPositionsAndTemplate();
        } catch (err) {
            window.app.showToast('Error al guardar plantilla: ' + err.message, 'error');
        }
    }

    async openPositionModal(pos = null) {
        const title = document.getElementById('modal-position-title');
        const idInput = document.getElementById('position-id');
        const nameInput = document.getElementById('position-name');
        const roleSelect = document.getElementById('position-role');
        const orderInput = document.getElementById('position-order');
        const isWeeklySelect = document.getElementById('position-is-weekly');

        // Cargar roles en el selector
        const roles = await window.api.getRoles();
        roleSelect.innerHTML = '';
        for (const r of roles) {
            const opt = document.createElement('option');
            opt.value = r.code;
            opt.textContent = `${r.name} (${r.code})`;
            roleSelect.appendChild(opt);
        }

        if (pos) {
            title.textContent = 'Editar Puesto';
            idInput.value = pos.id;
            nameInput.value = pos.name || '';
            roleSelect.value = pos.required_role || '';
            orderInput.value = pos.sort_order || 1;
            if (isWeeklySelect) isWeeklySelect.value = pos.is_weekly === 1 ? '1' : '0';
        } else {
            title.textContent = 'Nuevo Puesto de Guardia';
            idInput.value = '';
            nameInput.value = '';
            orderInput.value = this.positionsList.length + 1;
            if (isWeeklySelect) isWeeklySelect.value = '0';
        }

        window.app.openModal('modal-position');
    }

    async savePosition() {
        const nameInput = document.getElementById('position-name');
        const name = nameInput.value.trim();
        if (!name) {
            window.app.showToast('El nombre del puesto es requerido', 'error');
            nameInput.focus();
            return;
        }

        const id = document.getElementById('position-id').value;
        const role = document.getElementById('position-role').value;
        const order = parseInt(document.getElementById('position-order').value) || 1;
        const isWeeklySelect = document.getElementById('position-is-weekly');
        const isWeekly = isWeeklySelect ? parseInt(isWeeklySelect.value) : 0;

        const posData = {
            name,
            required_role: role,
            sort_order: order,
            is_weekly: isWeekly,
            is_active: 1
        };

        if (id) posData.id = parseInt(id);

        try {
            await window.api.savePosition(posData);
            window.app.closeModal('modal-position');
            window.app.showToast(id ? 'Puesto actualizado' : 'Puesto creado', 'success');
            await this.loadPositionsAndTemplate();
            if (window.scheduleManager) window.scheduleManager.loadAndRender();
        } catch (err) {
            window.app.showToast('Error al guardar puesto: ' + err.message, 'error');
        }
    }
}

// Instancia global
window.positionsManager = new PositionsManager();
