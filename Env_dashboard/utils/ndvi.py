# utils/ndvi.py
"""
Indicateur NDVI (Normalized Difference Vegetation Index)
"""
import ee
import streamlit as st
import folium
from streamlit_folium import folium_static
from .base import BaseIndicator
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import requests
import io
from PIL import Image


class NDVIIndicator(BaseIndicator):
    """Indice de végétation NDVI"""
    
    def __init__(self, palette_config):
        super().__init__("NDVI", palette_config)
        self.historical_collection = None
        
    def calculate(self, image, sensor_config):
        """Calcule le NDVI à partir de l'image"""
        try:
            if sensor_config["name"] == "MODIS":
                return image
            
            bands = sensor_config["bands"]
            ndvi = image.normalizedDifference([bands["nir"], bands["red"]]).rename('NDVI')
            return ndvi
        except Exception as e:
            st.error(f"Erreur calcul NDVI: {e}")
            return None
    
    # ==================== MÉTHODE ABSTRAITE REQUISE ====================
    def interpret(self, value):
        """
        Interprète la valeur NDVI - Méthode requise par BaseIndicator
        
        Args:
            value: Valeur NDVI à interpréter (float)
            
        Returns:
            str: Interprétation textuelle avec emoji
        """
        if isinstance(value, (int, float)):
            if value > 0.6:
                return "🌿 Très bonne végétation - Végétation dense et saine"
            elif value > 0.5:
                return "🟢 Bonne végétation - Végétation en bonne santé"
            elif value > 0.4:
                return "🍃 Végétation modérée - État satisfaisant"
            elif value > 0.3:
                return "🟡 Végétation clairsemée - Stress léger"
            elif value > 0.2:
                return "🟠 Végétation faible - Stress modéré"
            elif value > 0.1:
                return "🔴 Végétation très faible - Stress sévère"
            elif value >= 0:
                return "🏜️ Sol nu - Absence de végétation"
            else:
                return "💧 Eau - NDVI négatif"
        return "Valeur NDVI non interprétable"
    
    # ==================== VISUALISATION MATPLOTLIB ====================
    
    def display_matplotlib_visualization(self, ndvi_image, region, title="Analyse NDVI"):
        """
        Affiche une visualisation NDVI avec deux panneaux style matplotlib
        - Raw NDVI values (gauche)
        - Vegetation areas NDVI > 0.2 (droite)
        Légende compacte en bas de la figure
        """
        try:
            # Obtenir les bounds de la région
            bounds = region.bounds().getInfo()
            coords = bounds['coordinates'][0]
            
            lons = [coord[0] for coord in coords]
            lats = [coord[1] for coord in coords]
            min_lon, max_lon = min(lons), max(lons)
            min_lat, max_lat = min(lats), max(lats)
            
            # Créer un rectangle pour l'export
            export_region = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
            
            # Paramètres de visualisation NDVI
            vis_params = {
                'min': -0.5,
                'max': 0.8,
                'palette': ['#8B0000', '#D73027', '#F46D43', '#FDAE61', '#FEE08B', 
                            '#FFFFBF', '#D9EF8B', '#A6D96A', '#66BD63', '#1A9850', '#006837']
            }
            
            # Obtenir l'URL de la thumbnail
            url = ndvi_image.getThumbURL({
                'region': export_region,
                'dimensions': '800x600',
                'format': 'png',
                **vis_params
            })
            
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content))
                
                # Convertir en RGB si nécessaire
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                img_array = np.array(img)
                
                # Si l'image est en niveaux de gris (2D), la convertir en RGB
                if len(img_array.shape) == 2:
                    img_array = np.stack([img_array, img_array, img_array], axis=2)
                # Si l'image a 4 canaux (RGBA), prendre seulement RGB
                elif img_array.shape[2] == 4:
                    img_array = img_array[:, :, :3]
                
                # Créer la figure avec 2 sous-plots
                fig, axes = plt.subplots(1, 2, figsize=(16, 8))
                
                # ==================== PLOT 1: Raw NDVI ====================
                axes[0].imshow(img_array)
                axes[0].set_title("Raw NDVI Values", fontsize=14, fontweight="bold")
                axes[0].set_xlabel("Longitude", fontsize=11)
                axes[0].set_ylabel("Latitude", fontsize=11)
                axes[0].axis('off')
                
                # ==================== PLOT 2: Vegetation areas ====================
                r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]
                
                # Indice de végétation approximatif
                denominator = g + r + 0.001
                veg_index = (g - r) / denominator
                
                # Seuil pour la végétation (valeurs > 0.2)
                vegetation_mask = veg_index > 0.2
                
                # Créer l'affichage de la végétation
                vegetation_display = np.zeros_like(img_array)
                vegetation_display[vegetation_mask] = img_array[vegetation_mask]
                vegetation_display[~vegetation_mask] = [220, 220, 220]
                
                axes[1].imshow(vegetation_display)
                axes[1].set_title("Vegetation Areas (NDVI > 0.2)", fontsize=14, fontweight="bold")
                axes[1].set_xlabel("Longitude", fontsize=11)
                axes[1].set_ylabel("Latitude", fontsize=11)
                axes[1].axis('off')
                
                # ==================== LÉGENDE COMPACTE EN BAS ====================
                legend_elements = [
                    mpatches.Patch(color='#006837', label='🌿 Très bonne végétation (NDVI > 0.6)'),
                    mpatches.Patch(color='#A6D96A', label='🍃 Bonne végétation (NDVI 0.4-0.6)'),
                    mpatches.Patch(color='#FEE08B', label='🌾 Végétation modérée (NDVI 0.2-0.4)'),
                    mpatches.Patch(color='#D73027', label='🏜️ Végétation faible / Sol nu (NDVI < 0.2)'),
                    mpatches.Patch(color='#8B0000', label='💧 Eau')
                ]
                
                fig.legend(handles=legend_elements, 
                          loc='lower center', 
                          bbox_to_anchor=(0.5, -0.05),
                          ncol=3, 
                          fontsize=10,
                          title="📋 Légende NDVI",
                          title_fontsize=12,
                          frameon=True,
                          edgecolor='black',
                          shadow=True)
                
                # ==================== BARRE DE COULEUR GLOBALE ====================
                cbar_ax = fig.add_axes([0.3, 0.02, 0.4, 0.02])
                cmap = plt.cm.RdYlGn
                norm = plt.Normalize(-0.5, 0.8)
                cbar = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), 
                                   cax=cbar_ax, orientation='horizontal')
                cbar.set_label("NDVI Value", fontsize=11, fontweight='bold')
                cbar.ax.tick_params(labelsize=9)
                
                # Titre principal
                plt.suptitle(title, fontsize=16, fontweight="bold")
                
                # Ajustements
                plt.tight_layout()
                plt.subplots_adjust(bottom=0.15)
                
                return fig
            else:
                st.warning(f"Erreur téléchargement: {response.status_code}")
                return None
                
        except Exception as e:
            st.warning(f"Visualisation matplotlib non disponible: {str(e)[:100]}")
            return None
    
    # ==================== MÉTHODES EXISTANTES ====================
    
    def reclassify_absolute(self, ndvi_image, region):
        """
        Reclassification par seuils absolus avec clipping sur la région
        
        Classes:
        1: NDVI > 0.5 -> Normal
        2: NDVI 0.3-0.5 -> Vigilance  
        3: NDVI 0.2-0.3 -> Alerte
        4: NDVI < 0.2 -> Alerte critique
        """
        ndvi_clipped = ndvi_image.clip(region)
        
        normal = ndvi_clipped.gt(0.5)
        vigilance = ndvi_clipped.gt(0.3).And(ndvi_clipped.lte(0.5))
        alerte = ndvi_clipped.gt(0.2).And(ndvi_clipped.lte(0.3))
        critique = ndvi_clipped.lte(0.2)
        
        reclassified = ee.Image(1).where(normal, 1)\
                                 .where(vigilance, 2)\
                                 .where(alerte, 3)\
                                 .where(critique, 4)\
                                 .rename('NDVI_Alert_Class')
        
        return reclassified.clip(region)
    
    def calculate_anomaly(self, current_ndvi, start_date, end_date, region, sensor_config):
        """Calcule l'anomalie NDVI"""
        try:
            current_clipped = current_ndvi.clip(region)
            
            collection = ee.ImageCollection(sensor_config["collection"])
            collection = collection.filterDate(start_date, end_date)\
                                 .filterBounds(region)\
                                 .filterMetadata('CLOUD_COVER', 'less_than', sensor_config["max_cloud"])
            
            size = collection.size().getInfo()
            if size == 0:
                st.warning(f"Aucune donnée historique trouvée pour {start_date} à {end_date}")
                return None, None
            
            def add_ndvi(img):
                ndvi = self.calculate(img, sensor_config)
                return img.addBands(ndvi)
            
            ndvi_collection = collection.map(add_ndvi).select('NDVI')
            historical_mean = ndvi_collection.mean().rename('NDVI_Historical_Mean')
            anomaly = current_clipped.subtract(historical_mean).rename('NDVI_Anomaly')
            
            return anomaly.clip(region), historical_mean.clip(region)
            
        except Exception as e:
            st.error(f"Erreur calcul anomalie: {e}")
            return None, None
    
    def reclassify_anomaly(self, anomaly_image, region):
        """Reclassification des anomalies"""
        if anomaly_image is None:
            return None
        
        anomaly_clipped = anomaly_image.clip(region)
        
        normal = anomaly_clipped.gt(0)
        vigilance = anomaly_clipped.gt(-0.1).And(anomaly_clipped.lte(0))
        alerte = anomaly_clipped.gt(-0.2).And(anomaly_clipped.lte(-0.1))
        critique = anomaly_clipped.lte(-0.2)
        
        reclassified = ee.Image(1).where(normal, 1)\
                                 .where(vigilance, 2)\
                                 .where(alerte, 3)\
                                 .where(critique, 4)\
                                 .rename('Anomaly_Alert_Class')
        
        return reclassified.clip(region)
    
    def display_alert_map(self, alert_map, region, map_title="Carte des alertes", analysis_scale=500):
        """Affiche la carte des alertes"""
        try:
            vis_params = {
                'min': 1,
                'max': 4,
                'palette': ['#4CAF50', '#FFC107', '#FF9800', '#F44336']
            }
            
            bounds = region.bounds().getInfo()
            coords = bounds['coordinates'][0]
            
            lons = [coord[0] for coord in coords]
            lats = [coord[1] for coord in coords]
            center_lat = (min(lats) + max(lats)) / 2
            center_lon = (min(lons) + max(lons)) / 2
            
            lat_span = max(lats) - min(lats)
            lon_span = max(lons) - min(lons)
            zoom_start = self._calculate_zoom(lat_span, lon_span)
            
            m = folium.Map(
                location=[center_lat, center_lon], 
                zoom_start=zoom_start,
                control_scale=True
            )
            
            map_id = alert_map.getMapId(vis_params)
            
            folium.TileLayer(
                tiles=map_id['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=map_title,
                overlay=True,
                opacity=0.85
            ).add_to(m)
            
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                attr='Google Satellite',
                name='Satellite',
                overlay=False,
                control=True
            ).add_to(m)
            
            folium.LayerControl().add_to(m)
            self._add_legend(m)
            
            folium_static(m, width=900, height=650)
            
            return m
            
        except Exception as e:
            st.error(f"Erreur affichage carte: {e}")
            return None
    
    def _calculate_zoom(self, lat_span, lon_span):
        """Calcule le niveau de zoom automatique"""
        if lat_span < 0.01 and lon_span < 0.01:
            return 15
        elif lat_span < 0.05 and lon_span < 0.05:
            return 13
        elif lat_span < 0.2 and lon_span < 0.2:
            return 11
        elif lat_span < 0.5 and lon_span < 0.5:
            return 9
        elif lat_span < 1 and lon_span < 1:
            return 8
        elif lat_span < 2 and lon_span < 2:
            return 7
        elif lat_span < 5 and lon_span < 5:
            return 6
        else:
            return 5
    
    def _add_legend(self, map_object):
        """Ajoute une légende à la carte"""
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; 
                    right: 50px; 
                    z-index: 1000; 
                    background-color: white; 
                    padding: 15px;
                    border-radius: 8px;
                    border: 2px solid #ccc;
                    font-family: Arial;
                    font-size: 14px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
            <strong>🚨 Niveaux d'alerte NDVI</strong><br>
            <span style="color: #4CAF50;">🟢</span> Normal (NDVI > 0.5)<br>
            <span style="color: #FFC107;">🟡</span> Vigilance (0.3-0.5)<br>
            <span style="color: #FF9800;">🟠</span> Alerte (0.2-0.3)<br>
            <span style="color: #F44336;">🔴</span> Alerte critique (NDVI < 0.2)
        </div>
        '''
        map_object.get_root().html.add_child(folium.Element(legend_html))
    
    def get_alert_stats(self, alert_map, region, analysis_scale=500):
        """Calcule les statistiques des alertes"""
        try:
            histogram = alert_map.reduceRegion(
                reducer=ee.Reducer.frequencyHistogram(),
                geometry=region,
                scale=analysis_scale,
                maxPixels=1e9,
                bestEffort=True,
                tileScale=4
            )
            
            hist_data = histogram.getInfo()
            
            band_name = None
            for key in hist_data.keys():
                if 'Alert_Class' in key or 'NDVI_Alert' in key:
                    band_name = key
                    break
            
            if band_name and hist_data[band_name]:
                hist = hist_data[band_name]
                total = sum(hist.values())
                
                if total > 0:
                    stats = {
                        'Normal': (hist.get('1', 0) / total) * 100,
                        'Vigilance': (hist.get('2', 0) / total) * 100,
                        'Alerte': (hist.get('3', 0) / total) * 100,
                        'Alerte critique': (hist.get('4', 0) / total) * 100
                    }
                    return stats
                else:
                    st.warning("Aucun pixel valide trouvé dans la zone")
                    return None
            else:
                st.warning("Impossible de calculer les statistiques")
                return None
                
        except Exception as e:
            st.error(f"Erreur calcul stats: {e}")
            return None
    
    def get_stats_band_name(self):
        return 'NDVI'