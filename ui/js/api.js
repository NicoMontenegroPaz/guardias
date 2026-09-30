/**
 * API Bridge para comunicación entre la Interfaz Web y el Backend Python.
 * Soporta tanto PyWebView nativo (window.pywebview.api) como llamadas HTTP fetch de respaldo.
 */

class ApiBridge {
    constructor() {
        this.isPyWebView = false;
        this.checkPyWebView();
    }

    checkPyWebView() {
        if (window.pywebview && window.pywebview.api) {
            this.isPyWebView = true;
        }
    }

    async call(endpoint, params = {}) {
        // 1. Intentar usar pywebview.api nativo si está disponible
        if (window.pywebview && window.pywebview.api && typeof window.pywebview.api[endpoint] === 'function') {
            try {
                if (Array.isArray(params)) {
                    return await window.pywebview.api[endpoint](...params);
                } else if (Object.keys(params).length > 0) {
                    return await window.pywebview.api[endpoint](...Object.values(params));
                } else {
                    return await window.pywebview.api[endpoint]();
                }
            } catch (err) {
                console.error(`Error en llamada nativa ${endpoint}:`, err);
                throw err;
            }
        }

        // 2. Fallback a servidor HTTP local /api/
        try {
            const response = await fetch(`/api/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            });
            if (!response.ok) {
                throw new Error(`HTTP Error ${response.status}`);
            }
            return await response.json();
        } catch (err) {
            console.error(`Error en llamada HTTP ${endpoint}:`, err);
            throw err;
        }
    }

    // Métodos de Personal
    async getPersonnel(month = '') {
        return await this.call('get_personnel', { month });
    }

    async savePerson(personData) {
        return await this.call('save_person', { person_data: personData });
    }

    async deletePerson(personId) {
        return await this.call('delete_person', { person_id: personId });
    }

    // Métodos de Roles
    async getRoles() {
        return await this.call('get_roles', {});
    }

    async addRole(code, name, description = '') {
        return await this.call('add_role', { code, name, description });
    }

    // Métodos de Puestos
    async getPositions() {
        return await this.call('get_positions', {});
    }

    async savePosition(posData) {
        return await this.call('save_position', { pos_data: posData });
    }

    async deletePosition(posId) {
        return await this.call('delete_position', { pos_id: posId });
    }

    // Métodos de Plantilla Semanal
    async getWeeklyTemplate() {
        return await this.call('get_weekly_template', {});
    }

    async updateWeeklyTemplate(templateData) {
        return await this.call('update_weekly_template', { template_data: templateData });
    }

    async setDateOverride(dateStr, positionId, isEnabled) {
        return await this.call('set_date_override', { date_str: dateStr, position_id: positionId, is_enabled: isEnabled });
    }

    // Métodos de Feriados
    async getHolidays(year) {
        return await this.call('get_holidays_for_year', { year });
    }

    async saveCustomHoliday(dateStr, name) {
        return await this.call('save_custom_holiday', { date_str: dateStr, name });
    }

    async deleteCustomHoliday(holidayId) {
        return await this.call('delete_custom_holiday', { holiday_id: holidayId });
    }

    // Métodos de Cuadrante
    async getSchedule(startDate, endDate) {
        return await this.call('get_schedule', { start_date: startDate, end_date: endDate });
    }

    async generateSchedule(startDate, endDate, overwriteManual = false) {
        return await this.call('generate_schedule', { start_date: startDate, end_date: endDate, overwrite_manual: overwriteManual });
    }

    async updateAssignment(dateStr, positionId, personId, isManual = true) {
        return await this.call('update_assignment', { date_str: dateStr, position_id: positionId, person_id: personId, is_manual: isManual });
    }

    async assignWeeklyService(startDate, positionId, personId, isManual = true) {
        return await this.call('assign_weekly_service', { start_date: startDate, position_id: positionId, person_id: personId, is_manual: isManual });
    }

    async swapAssignments(date1, pos1Id, date2, pos2Id) {
        return await this.call('swap_assignments', { date1, pos1_id: pos1Id, date2, pos2_id: pos2Id });
    }

    async clearScheduleRange(startDate, endDate) {
        return await this.call('clear_schedule_range', { start_date: startDate, end_date: endDate });
    }

    async getConfig() {
        return await this.call('get_config', {});
    }

    async setConfig(weekStartDay) {
        return await this.call('set_config', { week_start_day: weekStartDay });
    }

    // Exportación
    async exportExcel(startDate, endDate) {
        return await this.call('export_excel', { start_date: startDate, end_date: endDate });
    }

    async exportCsv(startDate, endDate) {
        return await this.call('export_csv', { start_date: startDate, end_date: endDate });
    }
}

// Instancia global
window.api = new ApiBridge();
