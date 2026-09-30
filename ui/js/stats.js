/**
 * Módulo de Visualización de Estadísticas, Balance y Arrastre de Equidad.
 */

class StatsManager {
    constructor() {
        this.currentMonth = new Date().toISOString().slice(0, 7);
        this.init();
    }

    init() {
        this.setupMonthSelector();
    }

    setupMonthSelector() {
        const select = document.getElementById('balance-month-select');
        if (!select) return;

        const current = new Date();
        select.innerHTML = '';

        // Generar últimos 6 meses y próximos 3 meses
        for (let i = -6; i <= 3; i++) {
            const d = new Date(current.getFullYear(), current.getMonth() + i, 1);
            const mStr = d.toISOString().slice(0, 7);
            const opt = document.createElement('option');
            opt.value = mStr;
            const monthNames = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
            opt.textContent = `${monthNames[d.getMonth()]} ${d.getFullYear()}`;
            if (mStr === this.currentMonth) opt.selected = true;
            select.appendChild(opt);
        }

        select.addEventListener('change', (e) => {
            this.currentMonth = e.target.value;
            this.loadAndRenderStats();
        });
    }

    async loadAndRenderStats() {
        const chartContainer = document.getElementById('balance-chart-container');
        const detailsContainer = document.getElementById('equity-details-table-container');

        if (!chartContainer) return;

        try {
            const personnel = await window.api.getPersonnel(this.currentMonth);
            const activePersonnel = personnel.filter(p => p.is_active);

            // Ordenar por total de guardias descendente
            activePersonnel.sort((a, b) => b.month_total_guards - a.month_total_guards);

            // 1. RENDERIZAR BARRAS COMPARATIVAS
            if (activePersonnel.length === 0) {
                chartContainer.innerHTML = '<div style="color:#94a3b8; padding:20px;">No hay datos de personal activo.</div>';
                return;
            }

            const maxGuards = Math.max(...activePersonnel.map(p => p.month_total_guards || 0), 1);

            let chartHtml = '';
            for (const p of activePersonnel) {
                const total = p.month_total_guards || 0;
                const weekday = p.month_weekday_guards || 0;
                const special = p.month_special_guards || 0;

                const weekdayPercent = total > 0 ? (weekday / total) * 100 : 0;
                const specialPercent = total > 0 ? (special / total) * 100 : 0;
                const barWidth = ((total / maxGuards) * 100).toFixed(0);

                chartHtml += `
                    <div class="balance-bar-row">
                        <div class="balance-bar-meta">
                            <span><strong>${p.name}</strong> <small style="color:#94a3b8;">(${p.rank || '—'})</small></span>
                            <span><strong>${total}</strong> guardias <small style="color:#38bdf8;">(${weekday} háb. | ${special} finde/fer.)</small></span>
                        </div>
                        <div class="balance-bar-track" style="width: ${Math.max(15, barWidth)}%;">
                            <div class="bar-segment-weekday" style="width: ${weekdayPercent}%;" title="Días Hábiles: ${weekday}"></div>
                            <div class="bar-segment-special" style="width: ${specialPercent}%;" title="Finde / Feriados: ${special}"></div>
                        </div>
                    </div>
                `;
            }

            chartContainer.innerHTML = chartHtml;

            // 2. RENDERIZAR TABLA DE BALANCE ACUMULADO HISTÓRICO
            if (detailsContainer) {
                let tableHtml = `
                    <table class="data-table" style="font-size: 0.82rem; margin-top: 10px;">
                        <thead>
                            <tr>
                                <th>Integrante</th>
                                <th class="text-center">Histórico Hábiles</th>
                                <th class="text-center">Histórico Finde/Fer.</th>
                                <th class="text-center">Total Acumulado</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                for (const p of activePersonnel) {
                    tableHtml += `
                        <tr>
                            <td><strong>${p.name}</strong></td>
                            <td class="text-center">${p.total_weekday_guards}</td>
                            <td class="text-center" style="color: #f59e0b; font-weight: 600;">${p.total_special_guards}</td>
                            <td class="text-center" style="font-weight: 700; color: #38bdf8;">${p.total_guards}</td>
                        </tr>
                    `;
                }

                tableHtml += '</tbody></table>';
                detailsContainer.innerHTML = tableHtml;
            }

        } catch (err) {
            console.error('Error al cargar balance:', err);
        }
    }
}

// Instancia global
window.statsManager = new StatsManager();
