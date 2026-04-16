# utils/stats.py
"""
Calcul des statistiques et analyses temporelles
"""
import ee
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st


def calculate_stats(image, geometry, scale=1000):
    """Calcule les statistiques d'une image"""
    try:
        if geometry.area().getInfo() > 1000000000:
            scale = max(scale, 500)
        
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                ee.Reducer.stdDev(), None, True
            ).combine(
                ee.Reducer.min(), None, True
            ).combine(
                ee.Reducer.max(), None, True
            ),
            geometry=geometry,
            scale=scale,
            bestEffort=True,
            maxPixels=1e10
        )
        return stats.getInfo()
    except Exception as e:
        return None


def compute_timeseries(geometry, indicator_key, sensor_config, start_year, end_year, cloud_threshold):
    """Calcule la série temporelle annuelle"""
    from .earth_engine import get_satellite_image, calculate_indicator, calculate_stats
    
    years = list(range(start_year, end_year + 1))
    values = []
    
    for y in years:
        try:
            # Pour LST, utiliser le mode annuel pour meilleure couverture
            if indicator_key == "LST":
                img, _ = get_satellite_image(geometry, sensor_config, y, month=None, annual=True, cloud_threshold=cloud_threshold)
            else:
                img, _ = get_satellite_image(geometry, sensor_config, y, month=6, annual=False, cloud_threshold=cloud_threshold)
            
            if img is None:
                values.append(None)
                continue
                
            result = calculate_indicator(img, sensor_config, indicator_key)
            if result is None:
                values.append(None)
                continue
                
            stats = calculate_stats(result, geometry, scale=500)
            if stats:
                if indicator_key == "NDVI":
                    val = stats.get('NDVI_mean', 0) or stats.get('NDVI', 0)
                elif indicator_key == "NDWI":
                    val = stats.get('NDWI_mean', 0) or stats.get('NDWI', 0)
                elif indicator_key == "LST":
                    val = stats.get('LST_mean', 0) or stats.get('LST', 0)
                else:
                    val = stats.get('temperature_mean', 0) or stats.get('temperature', 0)
                
                if val is not None and val != 0:
                    values.append(val)
                else:
                    values.append(None)
            else:
                values.append(None)
        except Exception as e:
            st.warning(f"Erreur pour l'année {y}: {str(e)[:50]}")
            values.append(None)
    
    return years, values


def compute_seasonal(geometry, indicator_key, sensor_config, year, cloud_threshold):
    """Calcule la variation saisonnière"""
    from .earth_engine import get_satellite_image, calculate_indicator, calculate_stats
    
    months = list(range(1, 13))
    month_names = ["Jan", "Fev", "Mar", "Avr", "Mai", "Juin", "Juil", "Aout", "Sep", "Oct", "Nov", "Dec"]
    values = []
    
    for m in months:
        try:
            # Pour LST, élargir la période pour meilleure couverture
            if indicator_key == "LST":
                # Utiliser une période de 3 mois autour du mois cible
                from datetime import datetime, timedelta
                current_date = datetime(year, m, 15)
                start_date = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
                end_date = (current_date + timedelta(days=30)).strftime("%Y-%m-%d")
                
                # Récupérer l'image avec période élargie
                collection = ee.ImageCollection(sensor_config["collection"]) \
                    .filterBounds(geometry) \
                    .filterDate(start_date, end_date)
                
                if sensor_config.get("cloud_filter"):
                    collection = collection.filter(ee.Filter.lt(sensor_config["cloud_filter"], cloud_threshold))
                
                size = collection.size().getInfo()
                if size == 0:
                    values.append(None)
                    continue
                
                img = collection.median().clip(geometry)
                result = calculate_indicator(img, sensor_config, indicator_key)
            else:
                img, _ = get_satellite_image(geometry, sensor_config, year, month=m, annual=False, cloud_threshold=cloud_threshold)
                if img is None:
                    values.append(None)
                    continue
                result = calculate_indicator(img, sensor_config, indicator_key)
            
            if result is None:
                values.append(None)
                continue
                
            stats = calculate_stats(result, geometry, scale=500)
            if stats:
                if indicator_key == "NDVI":
                    val = stats.get('NDVI_mean', 0) or stats.get('NDVI', 0)
                elif indicator_key == "NDWI":
                    val = stats.get('NDWI_mean', 0) or stats.get('NDWI', 0)
                elif indicator_key == "LST":
                    val = stats.get('LST_mean', 0) or stats.get('LST', 0)
                else:
                    val = stats.get('temperature_mean', 0) or stats.get('temperature', 0)
                
                if val is not None and val != 0:
                    values.append(val)
                else:
                    values.append(None)
            else:
                values.append(None)
        except Exception as e:
            st.warning(f"Erreur pour le mois {m}: {str(e)[:50]}")
            values.append(None)
    
    return months, month_names, values


def plot_timeseries(years, values, indicator_name, title=None):
    """Crée un graphique de série temporelle"""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Nettoyer les valeurs
    valid_years = []
    valid_values = []
    for y, v in zip(years, values):
        if v is not None and v != 0:
            valid_years.append(y)
            valid_values.append(v)
    
    if valid_years:
        ax.plot(valid_years, valid_values, marker='o', linewidth=2, markersize=8, color='#2E7D32')
        ax.fill_between(valid_years, valid_values, alpha=0.3, color='#2E7D32')
        ax.set_xlabel('Année', fontsize=12)
        
        # Ajuster le label selon l'indicateur
        if indicator_name == "LST":
            ax.set_ylabel('Température (°C)', fontsize=12)
        else:
            ax.set_ylabel(f'{indicator_name}', fontsize=12)
        
        if title:
            ax.set_title(title, fontsize=14, fontweight='bold')
        else:
            ax.set_title(f'Évolution temporelle de {indicator_name}', fontsize=14, fontweight='bold')
        
        ax.grid(True, alpha=0.3)
        
        # Ajouter les valeurs sur les points
        for x, y in zip(valid_years, valid_values):
            ax.annotate(f'{y:.2f}', (x, y), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=9)
        
        ax.set_xlim(min(valid_years)-0.5, max(valid_years)+0.5)
    else:
        ax.text(0.5, 0.5, 'Aucune donnée disponible', ha='center', va='center', transform=ax.transAxes)
        ax.set_xlabel('Année', fontsize=12)
        if indicator_name == "LST":
            ax.set_ylabel('Température (°C)', fontsize=12)
        else:
            ax.set_ylabel(f'{indicator_name}', fontsize=12)
    
    plt.tight_layout()
    return fig


def plot_seasonal(months, month_names, values, indicator_name, title=None, year=None):
    """Crée un graphique de variation saisonnière"""
    fig, ax = plt.subplots(figsize=(12, 5))
    
    # Nettoyer les valeurs
    valid_names = []
    valid_values = []
    for m, n, v in zip(months, month_names, values):
        if v is not None and v != 0:
            valid_names.append(n)
            valid_values.append(v)
    
    if valid_values:
        bars = ax.bar(valid_names, valid_values, color='#2E7D32', alpha=0.7, edgecolor='black', linewidth=1)
        ax.set_xlabel('Mois', fontsize=12)
        
        # Ajuster le label selon l'indicateur
        if indicator_name == "LST":
            ax.set_ylabel('Température (°C)', fontsize=12)
        else:
            ax.set_ylabel(f'{indicator_name}', fontsize=12)
        
        if title:
            ax.set_title(title, fontsize=14, fontweight='bold')
        elif year:
            ax.set_title(f'Variation saisonnière de {indicator_name} - {year}', fontsize=14, fontweight='bold')
        else:
            ax.set_title(f'Variation saisonnière de {indicator_name}', fontsize=14, fontweight='bold')
        
        ax.grid(True, alpha=0.3, axis='y')
        
        # Ajouter les valeurs sur les barres
        for bar, val in zip(bars, valid_values):
            height = bar.get_height()
            ax.annotate(f'{val:.2f}', xy=(bar.get_x() + bar.get_width()/2, height),
                       xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9)
        
        # Ajuster l'axe Y
        y_max = max(valid_values) if valid_values else 1
        ax.set_ylim(0, y_max * 1.15)
        plt.xticks(rotation=45, ha='right')
    else:
        ax.text(0.5, 0.5, 'Aucune donnée disponible', ha='center', va='center', transform=ax.transAxes)
        ax.set_xlabel('Mois', fontsize=12)
        if indicator_name == "LST":
            ax.set_ylabel('Température (°C)', fontsize=12)
        else:
            ax.set_ylabel(f'{indicator_name}', fontsize=12)
        plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    return fig