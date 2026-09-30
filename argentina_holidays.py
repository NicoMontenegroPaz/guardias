"""
Módulo para el manejo y cálculo de Feriados Nacionales de la República Argentina y Fines de Semana.
Utiliza la librería `holidays` e integra feriados inamovibles, trasladables, puentes turísticos y feriados personalizados.
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
import holidays

class ArgentinaHolidayManager:
    """Gestiona feriados oficiales de Argentina y feriados personalizados."""

    def __init__(self, custom_holidays_provider=None):
        self._cache_years: Dict[int, Any] = {}
        self.custom_holidays_provider = custom_holidays_provider

    def _get_holidays_for_year(self, year: int):
        if year not in self._cache_years:
            # Instanciamos feriados de Argentina para el año solicitado
            ar_holidays = holidays.Argentina(years=year, language="es")
            self._cache_years[year] = ar_holidays
        return self._cache_years[year]

    def is_weekend(self, dt: date) -> bool:
        """Devuelve True si el día es Sábado (5) o Domingo (6)."""
        return dt.weekday() in (5, 6)

    def get_holiday_name(self, dt: date) -> Optional[str]:
        """Devuelve el nombre del feriado si existe, o None."""
        # 1. Verificar feriados personalizados de la base de datos si existe el proveedor
        if self.custom_holidays_provider:
            custom_name = self.custom_holidays_provider(dt)
            if custom_name:
                return custom_name

        # 2. Verificar feriados oficiales de Argentina
        try:
            ar_holidays = self._get_holidays_for_year(dt.year)
            if dt in ar_holidays:
                return ar_holidays.get(dt)
        except Exception:
            pass
        return None

    def is_holiday(self, dt: date) -> bool:
        """Devuelve True si la fecha es un feriado nacional o personalizado."""
        return self.get_holiday_name(dt) is not None

    def get_day_info(self, dt: date) -> Dict[str, Any]:
        """
        Retorna información completa sobre el día:
        - is_weekend: bool
        - is_holiday: bool
        - is_special: bool (weekend o feriado)
        - holiday_name: str | None
        - day_type: 'weekday' | 'weekend' | 'holiday'
        - weekday_name: str en español
        """
        weekday_idx = dt.weekday()
        weekday_names = [
            "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
        ]
        weekday_name = weekday_names[weekday_idx]
        is_wknd = weekday_idx in (5, 6)
        hol_name = self.get_holiday_name(dt)
        is_hol = hol_name is not None

        day_type = "weekday"
        if is_hol:
            day_type = "holiday"
        elif is_wknd:
            day_type = "weekend"

        return {
            "date": dt.strftime("%Y-%m-%d"),
            "day": dt.day,
            "month": dt.month,
            "year": dt.year,
            "weekday": weekday_idx,
            "weekday_name": weekday_name,
            "is_weekend": is_wknd,
            "is_holiday": is_hol,
            "is_special": is_wknd or is_hol,  # Computa como Guardia de Fin de Semana / Feriado
            "holiday_name": hol_name,
            "day_type": day_type
        }

    def get_holidays_in_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Retorna la lista de feriados en un rango de fechas."""
        res = []
        curr = start_date
        while curr <= end_date:
            info = self.get_day_info(curr)
            if info["is_holiday"]:
                res.append(info)
            curr += timedelta(days=1)
        return res


# Instancia global utilitaria
holiday_manager = ArgentinaHolidayManager()
