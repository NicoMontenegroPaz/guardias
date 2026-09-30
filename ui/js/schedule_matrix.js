/**
 * Módulo de Gestión y Renderizado del Cuadrante de Guardias (Matriz).
 * Controla la visualización por días y puestos, reemplazos manuales, asignación en bloque de semanas
 * e intercambios de turno.
 */

class ScheduleMatrixManager {
    constructor() {
        this.currentHorizon = 'month'; // '7', '14', '21', 'month'
        this.startDate = '';
        this.endDate = '';
        this.currentScheduleData = null;
        this.highlightedPersonId = null;
        this.activeCellContext = null;

        this.init();
    }

    init() {
        this.setupInitialDates();
        this.bindEvents();
    }

    setupInitialDates() {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        
        const monthPicker = document.getElementById('cuadrante-month-picker');
        if (monthPicker) {
            monthPicker.value = `${year}-${month}`;
        }
        
        this.calculateDateRange();
    }

    calculateDateRange() {
        const monthPicker = document.getElementById('cuadrante-month-picker');
        const [yearStr, monthStr] = (monthPicker.value || new Date().toISOString().slice(0, 7)).split('-');
        const year = parseInt(yearStr);
        const month = parseInt(monthStr);

        if (this.currentHorizon === 'month') {
            // Primer y último día del mes seleccionado
            const firstDay = new Date(year, month - 1, 1);
            const lastDay = new Date(year, month, 0);
            
            this.startDate = this.formatDate(firstDay);
            this.endDate = this.formatDate(lastDay);
        } else {
            const daysCount = parseInt(this.currentHorizon);
            const firstDay = new Date(year, month - 1, 1);
            const endDay = new Date(firstDay);
            endDay.setDate(firstDay.getDate() + daysCount - 1);

            this.startDate = this.formatDate(firstDay);
            this.endDate = this.formatDate(endDay);
        }
    }

    formatDate(dateObj) {
        const y = dateObj.getFullYear();
        const m = String(dateObj.getMonth() + 1).padStart(2, '0');
        const d = String(dateObj.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    bindEvents() {
        // Selector de horizonte (1 semana, 2 semanas, 3 semanas, mes)
        document.querySelectorAll('.horizon-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.horizon-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentHorizon = btn.dataset.days;
                this.calculateDateRange();
                this.loadAndRender();
            });
        });

        // Selector de mes
        const monthPicker = document.getElementById('cuadrante-month-picker');
        if (monthPicker) {
            monthPicker.addEventListener('change', () => {
                this.calculateDateRange();
                this.loadAndRender();
                if (window.personnelManager) {
                    window.personnelManager.loadPersonnel(monthPicker.value);
                }
            });
        }

        // Navegación de mes anterior / siguiente
        document.getElementById('btn-prev-period')?.addEventListener('click', () => this.navigateMonth(-1));
        document.getElementById('btn-next-period')?.addEventListener('click', () => this.navigateMonth(1));
        document.getElementById('btn-current-period')?.addEventListener('click', () => {
            this.setupInitialDates();
            this.loadAndRender();
        });

        // Botón de refresco
        document.getElementById('btn-refresh-matrix')?.addEventListener('click', () => this.loadAndRender());

        // Resaltar integrante
        const highlightSelect = document.getElementById('select-highlight-person');
        if (highlightSelect) {
            highlightSelect.addEventListener('change', (e) => {
                this.highlightedPersonId = e.target.value ? parseInt(e.target.value) : null;
                this.applyHighlighting();
            });
        }

        // Exportar Excel
        document.getElementById('btn-export-excel')?.addEventListener('click', async () => {
            try {
                window.app.showToast('Generando archivo Excel...', 'warning');
                const res = await window.api.exportExcel(this.startDate, this.endDate);
                if (res.success) {
                    window.app.showToast(`Archivo Excel exportado con éxito en: ${res.filename}`, 'success');
                } else {
                    window.app.showToast(`Error al exportar: ${res.error}`, 'error');
                }
            } catch (err) {
                window.app.showToast('Error al exportar a Excel', 'error');
            }
        });

        // Exportar CSV
        document.getElementById('btn-export-csv')?.addEventListener('click', async () => {
            try {
                window.app.showToast('Generando archivo CSV...', 'warning');
                const res = await window.api.exportCsv(this.startDate, this.endDate);
                if (res.success) {
                    window.app.showToast(`Archivo CSV guardado: ${res.filename}`, 'success');
                }
            } catch (err) {
                window.app.showToast('Error al exportar CSV', 'error');
            }
        });

        // Imprimir / PDF
        document.getElementById('btn-print-schedule')?.addEventListener('click', () => {
            window.print();
        });

        // Botón de desasignar en modal de celda
        document.getElementById('btn-cell-unassign')?.addEventListener('click', async () => {
            if (!this.activeCellContext) return;
            const { date, positionId, isWeekly } = this.activeCellContext;
            if (isWeekly) {
                await window.api.assignWeeklyService(date, positionId, null, true);
                window.app.showToast('Semana desasignada', 'warning');
            } else {
                await window.api.updateAssignment(date, positionId, null, true);
                window.app.showToast('Puesto desasignado', 'warning');
            }
            window.app.closeModal('modal-cell-action');
            this.loadAndRender();
            if (window.personnelManager) window.personnelManager.loadPersonnel();
        });
    }

    navigateMonth(offset) {
        const monthPicker = document.getElementById('cuadrante-month-picker');
        const [yearStr, monthStr] = monthPicker.value.split('-');
        let year = parseInt(yearStr);
        let month = parseInt(monthStr) + offset;

        if (month > 12) {
            month = 1;
            year += 1;
        } else if (month < 1) {
            month = 12;
            year -= 1;
        }

        monthPicker.value = `${year}-${String(month).padStart(2, '0')}`;
        this.calculateDateRange();
        this.loadAndRender();
        if (window.personnelManager) {
            window.personnelManager.loadPersonnel(monthPicker.value);
        }
    }

    async loadAndRender() {
        const container = document.getElementById('schedule-matrix-container');
        if (!container) return;

        container.innerHTML = '<div class="loading-spinner">Cargando cuadrante de guardias...</div>';

        try {
            const data = await window.api.getSchedule(this.startDate, this.endDate);
            this.currentScheduleData = data;
            this.renderMatrix(data);
            this.populateHighlightDropdown();
        } catch (err) {
            container.innerHTML = `<div class="error-box">Error al cargar cuadrante: ${err.message}</div>`;
        }
    }

    renderMatrix(data) {
        const container = document.getElementById('schedule-matrix-container');
        const { days, positions, matrix } = data;

        if (!positions || positions.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No hay puestos de guardia activos configurados.</p>
                    <button class="btn btn-primary btn-sm" onclick="window.app.switchTab('puestos')">Configurar Puestos</button>
                </div>
            `;
            return;
        }

        let html = '<table class="matrix-table">';

        // 1. ENCABEZADO DE LA TABLA (Días)
        html += '<thead><tr>';
        html += '<th class="col-puesto-header">PUESTO / SERVICIO</th>';

        for (const day of days) {
            let thClass = 'th-day-weekday';
            let tagClass = '';
            let tagText = '';

            // Resaltar jueves (inicio de ciclo semanal)
            const isThursday = day.day_of_week === 3;

            if (day.is_holiday) {
                thClass = 'th-day-holiday';
                tagClass = 'day-tag-holiday';
                tagText = day.holiday_name || 'FERIADO';
            } else if (day.is_weekend) {
                thClass = 'th-day-weekend';
                tagClass = 'day-tag-weekend';
                tagText = day.weekday_name.substring(0, 3).toUpperCase();
            }

            if (isThursday) {
                thClass += ' th-thursday-cycle';
            }

            html += `
                <th class="${thClass}">
                    <div class="day-header-box" title="${day.is_holiday ? day.holiday_name : day.weekday_name} ${isThursday ? '(Inicio Ciclo Semanal)' : ''}">
                        <span class="day-name">${day.weekday_name.substring(0, 3)}</span>
                        <span class="day-number">${day.day}</span>
                        ${tagText ? `<span class="day-tag ${tagClass}">${tagText}</span>` : ''}
                        ${isThursday ? '<span class="day-tag day-tag-cycle">JUE</span>' : ''}
                    </div>
                </th>
            `;
        }
        html += '</tr></thead>';

        // 2. CUERPO DE LA TABLA (Filas por Puesto)
        html += '<tbody>';
        for (const pos of positions) {
            const posId = pos.id;
            const isWeekly = pos.is_weekly === 1;

            html += `<tr class="${isWeekly ? 'row-weekly-service' : 'row-daily-guard'}">`;
            
            // Celda de nombre de puesto (Fija a la izquierda)
            html += `
                <td class="cell-puesto ${isWeekly ? 'cell-puesto-weekly' : ''}">
                    <div class="puesto-title-wrapper">
                        <span class="puesto-title">${pos.name}</span>
                        <div class="puesto-tags-row">
                            <span class="puesto-role-tag">${pos.required_role}</span>
                            ${isWeekly ? '<span class="badge-tag badge-weekly-tag">SEMANA (JUE-MIÉ)</span>' : '<span class="badge-tag badge-daily-tag">DIARIO</span>'}
                        </div>
                    </div>
                </td>
            `;

            // Celdas de cada día
            for (const day of days) {
                const dateStr = day.date;
                const slot = matrix[posId] ? matrix[posId][dateStr] : null;
                const hasPerson = slot && slot.person_id;
                const personId = hasPerson ? slot.person_id : '';
                const personName = hasPerson ? slot.person_name : '';
                const personRank = hasPerson ? slot.person_rank : '';
                const isManual = slot && slot.is_manual;
                const isThursday = day.day_of_week === 3;

                html += `
                    <td class="cell-guardia ${isWeekly ? 'cell-weekly-slot' : ''} ${isThursday ? 'cell-thursday-start' : ''}" 
                        data-date="${dateStr}" 
                        data-position-id="${posId}" 
                        data-position-name="${pos.name}"
                        data-required-role="${pos.required_role}"
                        data-is-weekly="${isWeekly ? '1' : '0'}"
                        data-person-id="${personId}"
                        data-day-name="${day.weekday_name} ${day.day}/${day.month}"
                        data-is-special="${day.is_special ? '1' : '0'}"
                        data-holiday-name="${day.holiday_name || ''}">
                        
                        <div class="slot-badge ${hasPerson ? (isWeekly ? 'slot-weekly-assigned' : '') : 'slot-unassigned'}">
                            ${isManual ? '<span class="manual-tag" title="Reemplazo manual"></span>' : ''}
                            ${hasPerson ? `
                                <span class="slot-person-name">${personName}</span>
                                ${personRank ? `<span class="slot-person-rank">${personRank}</span>` : ''}
                            ` : `
                                <span>+ ${isWeekly ? 'Semana' : 'Asignar'}</span>
                            `}
                        </div>
                    </td>
                `;
            }

            html += '</tr>';
        }
        html += '</tbody></table>';

        container.innerHTML = html;

        // Asignar eventos de clic en celdas
        container.querySelectorAll('.cell-guardia').forEach(cell => {
            cell.addEventListener('click', () => this.handleCellClick(cell));
        });

        this.applyHighlighting();
    }

    async handleCellClick(cell) {
        const date = cell.dataset.date;
        const positionId = parseInt(cell.dataset.positionId);
        const positionName = cell.dataset.positionName;
        const requiredRole = cell.dataset.requiredRole;
        const isWeekly = cell.dataset.isWeekly === '1';
        const currentPersonId = cell.dataset.personId ? parseInt(cell.dataset.personId) : null;
        const dayName = cell.dataset.dayName;
        const holidayName = cell.dataset.holidayName;
        const isSpecial = cell.dataset.isSpecial === '1';

        this.activeCellContext = { date, positionId, positionName, requiredRole, isWeekly, currentPersonId };

        // Configurar banner contextual del modal
        const banner = document.getElementById('cell-context-banner');
        if (banner) {
            banner.innerHTML = `
                <div style="font-weight: 700; font-size: 0.95rem; color: #ffffff;">
                    📅 ${dayName} ${holidayName ? `— <span style="color: #f59e0b;">Feriado: ${holidayName}</span>` : (isSpecial ? '— Fin de Semana' : '— Día Hábil')}
                </div>
                <div style="margin-top: 6px; font-size: 0.85rem; color: #94a3b8;">
                    🛡️ Puesto: <strong style="color: #ffffff;">${positionName}</strong> &nbsp;|&nbsp; Rol Requerido: <span class="puesto-role-tag">${requiredRole}</span>
                </div>
                ${isWeekly ? `
                    <div class="weekly-modal-notice">
                        ⭐ <strong>Servicio Semanal (Jueves a Miércoles):</strong> Al asignar un integrante, cubrirá los 7 días de la semana completa y quedará exento de guardias diarias durante todo el mes.
                    </div>
                ` : ''}
            `;
        }

        // Cargar lista de candidatos
        await this.renderCandidatesList(requiredRole, currentPersonId, isWeekly);

        window.app.openModal('modal-cell-action');
    }

    async renderCandidatesList(requiredRole, currentPersonId, isWeekly = false) {
        const listContainer = document.getElementById('candidate-selector-list');
        if (!listContainer) return;

        listContainer.innerHTML = '<div class="loading-spinner">Cargando integrantes...</div>';

        const monthStr = this.startDate.substring(0, 7);
        const personnel = await window.api.getPersonnel(monthStr);

        const eligible = [];
        const ineligible = [];

        for (const p of personnel) {
            if (!p.is_active) continue;
            const roles = Array.isArray(p.roles) ? p.roles : [];
            if (roles.includes(requiredRole)) {
                eligible.push(p);
            } else {
                ineligible.push(p);
            }
        }

        // Ordenar elegibles por menor carga
        if (isWeekly) {
            eligible.sort((a, b) => (a.month_weekly_services || 0) - (b.month_weekly_services || 0) || (a.total_weekly_services || 0) - (b.total_weekly_services || 0));
        } else {
            eligible.sort((a, b) => a.month_total_guards - b.month_total_guards || a.total_guards - b.total_guards);
        }

        let html = '';

        if (eligible.length === 0) {
            html += '<div style="padding: 10px; color: #f87171; font-size: 0.85rem;">⚠️ No hay personal activo registrado con el rol requerido (' + requiredRole + ').</div>';
        } else {
            html += `<div style="font-size: 0.75rem; color: #38bdf8; font-weight: 700; margin-bottom: 6px; text-transform: uppercase;">
                Personal Capacitado (Ordenado por Equidad de ${isWeekly ? 'Semanas' : 'Guardias'}):
            </div>`;
            
            for (const p of eligible) {
                const isCurrent = p.id === currentPersonId;
                const isWeeklyThisMonth = (p.month_weekly_services || 0) > 0;

                html += `
                    <div class="candidate-item ${isCurrent ? 'candidate-current' : ''}" data-person-id="${p.id}">
                        <div class="candidate-name-box">
                            <span class="candidate-name">${p.name} ${isCurrent ? '✓ (Asignado)' : ''}</span>
                            <span class="candidate-rank">${p.rank || 'Sin jerarquía'} • Roles: ${p.roles.join(', ')}</span>
                            ${isWeeklyThisMonth && !isWeekly ? '<span style="color:#f59e0b; font-size:0.75rem; display:block;">⚠️ Ya tiene una semana asignada este mes</span>' : ''}
                        </div>
                        <div class="candidate-stats-box">
                            <span class="stat-counter-pill pill-weekly" title="Semanas cumplidas en el mes">Sem: ${p.month_weekly_services || 0}</span>
                            <span class="stat-counter-pill pill-weekday" title="Guardias días hábiles en el mes">Háb: ${p.month_weekday_guards || 0}</span>
                            <span class="stat-counter-pill pill-special" title="Guardias finde/feriado en el mes">Finde: ${p.month_special_guards || 0}</span>
                        </div>
                    </div>
                `;
            }
        }

        listContainer.innerHTML = html;

        // Eventos de selección de candidato
        listContainer.querySelectorAll('.candidate-item').forEach(item => {
            item.addEventListener('click', async () => {
                const chosenPersonId = parseInt(item.dataset.personId);
                await this.assignPersonToCell(chosenPersonId);
            });
        });
    }

    async assignPersonToCell(personId) {
        if (!this.activeCellContext) return;
        const { date, positionId, isWeekly } = this.activeCellContext;

        try {
            if (isWeekly) {
                await window.api.assignWeeklyService(date, positionId, personId, true);
                window.app.showToast('Semana completa asignada (Jueves a Miércoles)', 'success');
            } else {
                await window.api.updateAssignment(date, positionId, personId, true);
                window.app.showToast('Guardia asignada / reemplazada correctamente', 'success');
            }
            
            window.app.closeModal('modal-cell-action');
            this.loadAndRender();
            if (window.personnelManager) window.personnelManager.loadPersonnel();
        } catch (err) {
            window.app.showToast('Error al asignar: ' + err.message, 'error');
        }
    }

    populateHighlightDropdown() {
        const select = document.getElementById('select-highlight-person');
        if (!select || !this.currentScheduleData) return;

        const currentVal = select.value;
        select.innerHTML = '<option value="">Resaltar integrante...</option>';

        if (window.personnelManager && window.personnelManager.personnelList) {
            for (const p of window.personnelManager.personnelList) {
                if (p.is_active) {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = `${p.name} (${p.rank || ''})`;
                    if (String(p.id) === String(currentVal)) opt.selected = true;
                    select.appendChild(opt);
                }
            }
        }
    }

    applyHighlighting() {
        const cells = document.querySelectorAll('.cell-guardia');
        cells.forEach(cell => {
            const pid = cell.dataset.personId ? parseInt(cell.dataset.personId) : null;
            if (this.highlightedPersonId && pid === this.highlightedPersonId) {
                cell.classList.add('highlighted-person');
            } else {
                cell.classList.remove('highlighted-person');
            }
        });
    }
}

// Instancia global
window.scheduleManager = new ScheduleMatrixManager();
