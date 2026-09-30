/**
 * Módulo de Gestión de Personal, Roles y Contadores de Guardias.
 * Permite altas, bajas, modificaciones, asignación de roles admitidos y seguimiento de equidad.
 */

class PersonnelManager {
    constructor() {
        this.personnelList = [];
        this.rolesList = [];
        this.currentMonth = new Date().toISOString().slice(0, 7);

        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        // Filtros de búsqueda
        document.getElementById('filter-person-search')?.addEventListener('input', () => this.filterAndRenderTable());
        document.getElementById('filter-person-role')?.addEventListener('change', () => this.filterAndRenderTable());
        document.getElementById('filter-person-status')?.addEventListener('change', () => this.filterAndRenderTable());

        // Botón Nuevo Integrante
        document.getElementById('btn-add-person')?.addEventListener('click', () => this.openPersonModal());

        // Botón Guardar Integrante
        document.getElementById('btn-save-person')?.addEventListener('click', () => this.savePerson());

        // Modal de Roles
        document.getElementById('btn-add-role')?.addEventListener('click', () => this.openRoleModal());
        document.getElementById('btn-save-role')?.addEventListener('click', () => this.saveRole());
    }

    openRoleModal() {
        document.getElementById('form-role').reset();
        document.getElementById('modal-role').classList.add('active');
    }

    async saveRole() {
        const codeInput = document.getElementById('role-code');
        const nameInput = document.getElementById('role-name');
        const descInput = document.getElementById('role-desc');

        if (!codeInput.checkValidity() || !nameInput.checkValidity()) {
            window.ui.showToast('Por favor, completa los campos obligatorios.', 'error');
            return;
        }

        const data = {
            code: codeInput.value.trim().toLowerCase(),
            name: nameInput.value.trim(),
            description: descInput.value.trim()
        };

        try {
            await window.api.addRole(data);
            window.ui.showToast('Rol agregado exitosamente.', 'success');
            document.getElementById('modal-role').classList.remove('active');
            this.loadRoles(); // Recargar la lista
            // Si las otras vistas necesitan actualizarse, podríamos lanzar un evento
            window.dispatchEvent(new Event('roles-updated'));
        } catch (err) {
            console.error(err);
            window.ui.showToast('Error al guardar el rol. Verifica que el código no esté duplicado.', 'error');
        }
    }

    async loadRoles() {
        try {
            this.rolesList = await window.api.getRoles();
            this.populateRoleFiltersAndCheckboxes();
        } catch (err) {
            console.error('Error al cargar roles:', err);
        }
    }

    populateRoleFiltersAndCheckboxes() {
        // 1. Selector de filtro en la tabla
        const roleFilter = document.getElementById('filter-person-role');
        if (roleFilter) {
            roleFilter.innerHTML = '<option value="">Todos los roles</option>';
            for (const r of this.rolesList) {
                const opt = document.createElement('option');
                opt.value = r.code;
                opt.textContent = r.name;
                roleFilter.appendChild(opt);
            }
        }

        // 2. Checkboxes en el modal de personal
        const container = document.getElementById('person-roles-container');
        if (container) {
            container.innerHTML = '';
            for (const r of this.rolesList) {
                const label = document.createElement('label');
                label.className = 'checkbox-container';
                label.innerHTML = `
                    <input type="checkbox" name="person-role-cb" value="${r.code}">
                    <span class="checkmark"></span>
                    <span><strong>${r.name}</strong> <small style="color:#64748b;">(${r.code})</small></span>
                `;
                container.appendChild(label);
            }
        }
    }

    async loadPersonnel(month = '') {
        if (month) this.currentMonth = month;
        try {
            await this.loadRoles();
            this.personnelList = await window.api.getPersonnel(this.currentMonth);
            this.updateStatsCards();
            this.filterAndRenderTable();
            if (window.scheduleManager) {
                window.scheduleManager.populateHighlightDropdown();
            }
        } catch (err) {
            console.error('Error al cargar personal:', err);
        }
    }

    updateStatsCards() {
        const activePersonnel = this.personnelList.filter(p => p.is_active);
        const totalActive = activePersonnel.length;
        
        let totalMonthGuards = 0;
        let totalWeekendGuards = 0;
        let totalWeeklyServices = 0;

        for (const p of activePersonnel) {
            totalMonthGuards += p.month_total_guards || 0;
            totalWeekendGuards += p.month_special_guards || 0;
            totalWeeklyServices += p.month_weekly_services || 0;
        }

        const avg = totalActive > 0 ? (totalMonthGuards / totalActive).toFixed(1) : '0.0';

        // Calcular índice de equidad (desviación estándar de guardias diarias)
        let equityScore = 100;
        if (totalActive > 1 && totalMonthGuards > 0) {
            const mean = totalMonthGuards / totalActive;
            let variance = 0;
            for (const p of activePersonnel) {
                variance += Math.pow((p.month_total_guards || 0) - mean, 2);
            }
            const stdDev = Math.sqrt(variance / totalActive);
            equityScore = Math.max(0, Math.min(100, Math.round(100 - (stdDev * 15))));
        }

        document.getElementById('stat-total-personnel').textContent = totalActive;
        document.getElementById('stat-avg-guards').textContent = avg;
        document.getElementById('stat-total-weekend-guards').textContent = totalWeekendGuards;
        document.getElementById('stat-equity-score').textContent = `${equityScore}%`;
    }

    filterAndRenderTable() {
        const search = (document.getElementById('filter-person-search')?.value || '').toLowerCase().trim();
        const roleFilter = document.getElementById('filter-person-role')?.value || '';
        const statusFilter = document.getElementById('filter-person-status')?.value || 'all';

        const filtered = this.personnelList.filter(p => {
            // Filtro por texto
            const matchesSearch = !search || 
                p.name.toLowerCase().includes(search) || 
                (p.dni && p.dni.toLowerCase().includes(search)) ||
                (p.rank && p.rank.toLowerCase().includes(search));

            // Filtro por rol
            const pRoles = Array.isArray(p.roles) ? p.roles : [];
            const matchesRole = !roleFilter || pRoles.includes(roleFilter);

            // Filtro por estado
            let matchesStatus = true;
            if (statusFilter === 'active') matchesStatus = p.is_active === 1;
            if (statusFilter === 'inactive') matchesStatus = p.is_active === 0;

            return matchesSearch && matchesRole && matchesStatus;
        });

        this.renderTable(filtered);
    }

    renderTable(list) {
        const tbody = document.getElementById('personnel-table-body');
        if (!tbody) return;

        if (list.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="11" class="text-center" style="padding: 30px; color: #94a3b8;">
                        No se encontraron integrantes que coincidan con los filtros aplicados.
                    </td>
                </tr>
            `;
            return;
        }

        // Calcular promedio del mes para el indicador de equidad
        const activePersonnel = this.personnelList.filter(p => p.is_active);
        const totalActive = activePersonnel.length;
        const totalMonthGuards = activePersonnel.reduce((acc, p) => acc + (p.month_total_guards || 0), 0);
        const avgMonth = totalActive > 0 ? totalMonthGuards / totalActive : 0;

        let html = '';
        for (const p of list) {
            const roles = Array.isArray(p.roles) ? p.roles : [];
            const rolesBadges = roles.map(r => `<span class="badge-tag badge-role">${r}</span>`).join(' ') || '<span style="color:#64748b; font-size:0.75rem;">Sin roles</span>';

            // Indicador de balance relativo a la media
            const diff = (p.month_total_guards || 0) - avgMonth;
            let equityHtml = '';
            if (p.month_weekly_services > 0) {
                equityHtml = '<span class="equity-indicator equity-weekly" title="Cubrió servicio semanal">★ De Semana</span>';
            } else if (Math.abs(diff) < 0.6) {
                equityHtml = '<span class="equity-indicator equity-balanced" title="Carga equilibrada">● En Paridad</span>';
            } else if (diff > 0) {
                equityHtml = `<span class="equity-indicator equity-over" title="Tiene más guardias que la media">+${diff.toFixed(1)}</span>`;
            } else {
                equityHtml = `<span class="equity-indicator equity-under" title="Tiene menos guardias que la media">${diff.toFixed(1)}</span>`;
            }

            html += `
                <tr>
                    <td>
                        <div style="font-weight: 600; color: #ffffff;">${p.name}</div>
                        ${p.dni ? `<div style="font-size: 0.75rem; color: #64748b;">DNI: ${p.dni}</div>` : ''}
                    </td>
                    <td><span style="font-weight: 500; color: #cbd5e1;">${p.rank || '—'}</span></td>
                    <td>${rolesBadges}</td>
                    <td class="text-center">
                        <span class="stat-counter-pill pill-weekly">${p.month_weekly_services || 0}</span>
                    </td>
                    <td class="text-center">
                        <span class="stat-counter-pill pill-weekday">${p.month_weekday_guards}</span>
                    </td>
                    <td class="text-center">
                        <span class="stat-counter-pill pill-special">${p.month_special_guards}</span>
                    </td>
                    <td class="text-center">
                        <span class="stat-counter-pill pill-total">${p.month_total_guards}</span>
                    </td>
                    <td class="text-center" style="font-size: 0.8rem; color: #94a3b8;">
                        Háb: ${p.total_weekday_guards} | Finde: ${p.total_special_guards} <br>
                        <strong>Total: ${p.total_guards}</strong> (Sem: ${p.total_weekly_services || 0})
                    </td>
                    <td class="text-center">${equityHtml}</td>
                    <td class="text-center">
                        <span class="badge-tag ${p.is_active ? 'badge-active' : 'badge-inactive'}">
                            ${p.is_active ? 'Activo' : 'Licencia'}
                        </span>
                    </td>
                    <td class="text-right">
                        <button class="btn btn-sm btn-outline btn-edit-person" data-id="${p.id}" title="Editar">
                            ✏️ Editar
                        </button>
                        <button class="btn btn-sm btn-ghost btn-delete-person" data-id="${p.id}" title="Eliminar" style="color:#ef4444;">
                            🗑️
                        </button>
                    </td>
                </tr>
            `;
        }

        tbody.innerHTML = html;

        // Asignar eventos de botones de acción
        tbody.querySelectorAll('.btn-edit-person').forEach(btn => {
            btn.addEventListener('click', () => {
                const pid = parseInt(btn.dataset.id);
                const person = this.personnelList.find(p => p.id === pid);
                if (person) this.openPersonModal(person);
            });
        });

        tbody.querySelectorAll('.btn-delete-person').forEach(btn => {
            btn.addEventListener('click', async () => {
                const pid = parseInt(btn.dataset.id);
                const person = this.personnelList.find(p => p.id === pid);
                if (person && confirm(`¿Estás seguro de eliminar a ${person.name}? Sus asignaciones históricas se preservarán.`)) {
                    await window.api.deletePerson(pid);
                    window.app.showToast('Integrante eliminado', 'warning');
                    this.loadPersonnel();
                    if (window.scheduleManager) window.scheduleManager.loadAndRender();
                }
            });
        });
    }

    openPersonModal(person = null) {
        const title = document.getElementById('modal-person-title');
        const idInput = document.getElementById('person-id');
        const nameInput = document.getElementById('person-name');
        const dniInput = document.getElementById('person-dni');
        const rankInput = document.getElementById('person-rank');
        const activeSelect = document.getElementById('person-active');
        const notesInput = document.getElementById('person-notes');

        if (person) {
            title.textContent = 'Editar Integrante';
            idInput.value = person.id;
            nameInput.value = person.name || '';
            dniInput.value = person.dni || '';
            rankInput.value = person.rank || '';
            activeSelect.value = person.is_active ? '1' : '0';
            notesInput.value = person.notes || '';

            const roles = Array.isArray(person.roles) ? person.roles : [];
            document.querySelectorAll('input[name="person-role-cb"]').forEach(cb => {
                cb.checked = roles.includes(cb.value);
            });
        } else {
            title.textContent = 'Nuevo Integrante';
            idInput.value = '';
            nameInput.value = '';
            dniInput.value = '';
            rankInput.value = '';
            activeSelect.value = '1';
            notesInput.value = '';

            document.querySelectorAll('input[name="person-role-cb"]').forEach(cb => {
                cb.checked = false;
            });
        }

        window.app.openModal('modal-person');
    }

    async savePerson() {
        const nameInput = document.getElementById('person-name');
        const name = nameInput.value.trim();
        if (!name) {
            window.app.showToast('El nombre es obligatorio', 'error');
            nameInput.focus();
            return;
        }

        const id = document.getElementById('person-id').value;
        const dni = document.getElementById('person-dni').value.trim();
        const rank = document.getElementById('person-rank').value.trim();
        const isActive = document.getElementById('person-active').value === '1';
        const notes = document.getElementById('person-notes').value.trim();

        const selectedRoles = [];
        document.querySelectorAll('input[name="person-role-cb"]:checked').forEach(cb => {
            selectedRoles.push(cb.value);
        });

        if (selectedRoles.length === 0) {
            window.app.showToast('Debes seleccionar al menos un rol admitido para este integrante', 'warning');
            return;
        }

        const personData = {
            name,
            dni,
            rank,
            roles: selectedRoles,
            is_active: isActive,
            notes
        };

        if (id) {
            personData.id = parseInt(id);
        }

        try {
            await window.api.savePerson(personData);
            window.app.closeModal('modal-person');
            window.app.showToast(id ? 'Integrante actualizado con éxito' : 'Integrante agregado con éxito', 'success');
            await this.loadPersonnel();
            if (window.scheduleManager) window.scheduleManager.loadAndRender();
        } catch (err) {
            window.app.showToast('Error al guardar integrante: ' + err.message, 'error');
        }
    }
}

// Instancia global
window.personnelManager = new PersonnelManager();
