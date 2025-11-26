# -*- coding: utf-8 -*-
"""
ETL para cargar los datos de KPIs y Sitios a una base de datos SQLite.

Versión final: limpia, sobria y sin mensajes de depuración.
"""

import pandas as pd
import sqlite3
from pathlib import Path
import warnings

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# --- 1. Constantes ---
DB_NAME = "kpi_data.db"
DB_PATH = Path(DB_NAME)

KPI_FILE = "contadores-22-oct-5-nov.xlsx"
SITE_FILE = "pruebas-sitios.xlsx"

KPI_SHEET_NAME = "Datos"
SITE_SHEET_NAME = "Datos"

KPI_TABLE = "kpi_data"
SITE_TABLE = "site_data"

# --- 2. Carga de datos KPI ---
def load_kpi_data(file_path, sheet_name):
    """
    Carga los datos de KPIs desde el archivo Excel.
    La primera columna contiene fecha y hora en formato dd/mm/yyyy hh:mm:ss.
    """
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')

        # La primera columna contiene la fecha y hora
        first_col = df.columns[0]

        # Conversión robusta a datetime usando formato dd/mm/yyyy hh:mm:ss
        df[first_col] = pd.to_datetime(df[first_col], format='%d/%m/%Y %H:%M:%S', errors='coerce')

        # Verificar conversión exitosa
        if not pd.api.types.is_datetime64_any_dtype(df[first_col]):
            print(f"Error: No se pudo convertir la columna '{first_col}' a formato datetime.")
            return None

        # Separar fecha y hora en columnas nuevas (sin sobrescribir la columna original)
        df['Date'] = df[first_col].dt.strftime('%d/%m/%Y')
        df['Hora'] = df[first_col].dt.strftime('%H:%M:%S')

        # Columnas esperadas en orden
        expected_cols = [
            'Date',
            'Hora',
            'Site Id',
            'Sector',
            'DENOM_CELL_AVAIL',
            'SAMPLES_CELL_AVAIL',
            'NG_FLOW_REL_AMF_UE_LOST',
            'NG_FLOW_REL_NORMAL',
            'NG_FLOW_REL',
            'NG_FLOW_REL_AMF_OTHER',
            'NG_FLOW_REL_AMF_OTHER_5QI1',
            'NRRCC_RRC_STPREQ_MO_SIGNALLING',
            'NRRCC_RRC_STPREQ_MO_DATA',
            'NRRCC_RRC_STPREQ_MT_ACCESS',
            'NRRCC_RRC_STPREQ_EMERGENCY',
            'NRRCC_RRC_STPREQ_HIPRIO_ACCESS',
            'NRRCC_RRC_STPREQ_MO_VOICECALL',
            'NRRCC_RRC_STPREQ_MO_SMS',
            'NRRCC_RRC_STPREQ_MPS',
            'NRRCC_RRC_STPREQ_MCS',
            'NRRCC_RRC_STPREQ_MO_VIDEOCAL',
            'NRRCC_RRC_STPSUCC_TOT',
            'REESTAB_ACC_FALLBACK',
            'NRRCC_RRC_RESUME_FALLBACK_SUCC',
            'NNGCC_INIT_UE_MSG_SENT',
            'NNGCC_UE_LOGICAL_CONN_ESTAB',
            'NNGCC_UE_CTXT_STP_REQ_RECD',
            'NNGCC_UE_CTXT_STP_RESP_SENT'
        ]

        df.rename(columns=lambda x: x.strip(), inplace=True)
        cols_final = [c for c in expected_cols if c in df.columns]
        df_final = df[cols_final].copy()

        df_final.dropna(subset=['Date', 'Hora'], inplace=True)
        return df_final

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo KPI '{file_path}'")
        return None
    except Exception as e:
        print(f"Error al procesar el archivo KPI: {e}")
        return None

# --- 3. Carga de datos de Sitios ---
def load_site_data(file_path, sheet_name):
    """
    Carga los datos de geolocalización de los sitios desde el archivo Excel.
    """
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')

        if 'ID' in df.columns:
            df.rename(columns={'ID': 'Site_id'}, inplace=True)

        if not all(col in df.columns for col in ['Site_id', 'Latitud', 'Longitud', 'Nombre']):
            print("Error: Columnas requeridas (Site_id, Latitud, Longitud, Nombre) no encontradas.")
            return None

        return df

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo de Sitios '{file_path}'")
        return None
    except Exception as e:
        print(f"Error al procesar el archivo de sitios: {e}")
        return None

# --- 4. Proceso principal ---
def main():
    print("Iniciando proceso ETL (Excel con separación de Date y Hora)...")

    if DB_PATH.exists():
        DB_PATH.unlink()

    df_kpi = load_kpi_data(KPI_FILE, KPI_SHEET_NAME)
    df_sites = load_site_data(SITE_FILE, SITE_SHEET_NAME)

    if df_kpi is None or df_sites is None:
        print("Proceso ETL fallido. No se creará la base de datos.")
        return

    try:
        with sqlite3.connect(DB_NAME) as conn:
            df_kpi.to_sql(KPI_TABLE, conn, if_exists='replace', index=False)
            df_sites.to_sql(SITE_TABLE, conn, if_exists='replace', index=False)

        with sqlite3.connect(DB_NAME) as conn:
            kpi_count = pd.read_sql(f"SELECT COUNT(*) FROM {KPI_TABLE}", conn).iloc[0, 0]
            site_count = pd.read_sql(f"SELECT COUNT(*) FROM {SITE_TABLE}", conn).iloc[0, 0]
            print(f"Base de datos '{DB_NAME}' creada exitosamente.")
            print(f"Registros en '{KPI_TABLE}': {kpi_count}")
            print(f"Registros en '{SITE_TABLE}': {site_count}")

    except Exception as e:
        print(f"Error al escribir en la base de datos SQLite: {e}")

if __name__ == "__main__":
    main()
