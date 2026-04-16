# utils/vci.py
"""
Indicateur VCI (Vegetation Condition Index) - Version MODIS
"""
import ee
import streamlit as st
from .base import BaseIndicator


class VCIIndicator(BaseIndicator):
    """Indice de condition de la végétation VCI"""
    
    def __init__(self, palette_config):
        super().__init__("VCI", palette_config)
        
    def calculate(self, image, sensor_config):
        st.warning("Le VCI nécessite une approche différente. Utilisez calculate_vci() à la place.")
        return None
    
    def calculate_vci(self, aoi, target_start, target_end, hist_start, hist_end):
        """
        Calcule le VCI avec MODIS - Les zones d'eau sont extraites et masquées
        """
        try:
            # ========== PÉRIODE HISTORIQUE ==========
            hist_collection = ee.ImageCollection("MODIS/006/MOD13Q1") \
                .filterBounds(aoi) \
                .filterDate(hist_start, hist_end) \
                .select('NDVI')
            
            hist_size = hist_collection.size().getInfo()
            st.info(f"📊 Période historique ({hist_start} à {hist_end}): {hist_size} images")
            
            if hist_size == 0:
                st.error(f"Aucune image MODIS trouvée pour {hist_start} à {hist_end}")
                return None, None, None, None, None
            
            def scale_ndvi(img):
                return img.multiply(0.0001).copyProperties(img, ['system:time_start'])
            
            hist_ndvi = hist_collection.map(scale_ndvi)
            
            # Masque de végétation : NDVI > 0.1 (exclut eau et sol nu)
            vegetation_mask = hist_ndvi.mean().gt(0.1)
            
            # Masque d'eau : NDVI <= 0.1
            water_mask = vegetation_mask.Not()
            
            # NDVI min et max (uniquement sur végétation)
            hist_masked = hist_ndvi.map(lambda img: img.updateMask(vegetation_mask))
            ndvi_min = hist_masked.min()
            ndvi_max = hist_masked.max()
            
            # ========== PÉRIODE CIBLE ==========
            target_collection = ee.ImageCollection("MODIS/006/MOD13Q1") \
                .filterBounds(aoi) \
                .filterDate(target_start, target_end) \
                .select('NDVI')
            
            target_size = target_collection.size().getInfo()
            st.info(f"🎯 Période cible ({target_start} à {target_end}): {target_size} images")
            
            if target_size == 0:
                st.warning(f"Aucune image MODIS pour {target_start} à {target_end}")
                year = target_start[:4]
                target_start = f"{year}-01-01"
                target_end = f"{year}-12-31"
                target_collection = ee.ImageCollection("MODIS/006/MOD13Q1") \
                    .filterBounds(aoi) \
                    .filterDate(target_start, target_end) \
                    .select('NDVI')
                target_size = target_collection.size().getInfo()
                if target_size == 0:
                    st.error(f"Aucune image MODIS pour l'année {year}")
                    return None, None, None, None, None
                st.info(f"✅ Utilisation de l'année complète {year}: {target_size} images")
            
            current_ndvi = target_collection.map(scale_ndvi).mean()
            
            # ========== CALCUL VCI (UNIQUEMENT SUR VÉGÉTATION) ==========
            vci = current_ndvi.subtract(ndvi_min) \
                .divide(ndvi_max.subtract(ndvi_min)) \
                .multiply(100) \
                .rename('VCI')
            
            # Appliquer le masque végétation (les zones d'eau seront transparentes/NODATA)
            vci = vci.updateMask(vegetation_mask)
            vci = vci.where(vci.lt(0), 0).where(vci.gt(100), 100)
            
            # ========== CLASSIFICATION VCI (UNIQUEMENT SUR VÉGÉTATION) ==========
            # Classes: 1=stress sévère, 2=stress modéré, 3=normal, 4=bon, 5=très bon
            # PAS DE CLASSE POUR L'EAU - L'EAU EST MASQUÉE
            vci_class = vci.expression(
                "(b <= 20) ? 1"
                ": (b <= 40) ? 2"
                ": (b <= 60) ? 3"
                ": (b <= 80) ? 4"
                ": 5",
                {'b': vci}
            ).rename('VCI_Class')
            
            # L'EAU N'EST PAS INCLUSE - les zones d'eau restent transparentes/NODATA
            
            # Appliquer les masques à la zone d'étude
            vci = vci.clip(aoi)
            vci_class = vci_class.clip(aoi)
            
            return vci, vci_class, ndvi_min, ndvi_max, current_ndvi
            
        except Exception as e:
            st.error(f"Erreur calcul VCI: {str(e)}")
            return None, None, None, None, None
    
    def get_class_name(self, class_value):
        classes = {
            1: "🔴 Stress sévère (0-20%)",
            2: "🟠 Stress modéré (20-40%)",
            3: "🟡 Condition normale (40-60%)",
            4: "🟢 Bon (60-80%)",
            5: "🌲 Très bon (80-100%)"
        }
        return classes.get(int(class_value), "Inconnu")
    
    def interpret(self, value):
        if value > 80:
            return "🌲 Végétation très saine", "success"
        elif value > 60:
            return "🟢 Végétation saine", "success"
        elif value > 40:
            return "🟡 Condition normale", "info"
        elif value > 20:
            return "🟠 Stress modéré", "warning"
        elif value > 0:
            return "🔴 Stress sévère", "error"
        else:
            return "💧 Eau (masquée)", "secondary"
    
    def get_stats_band_name(self):
        return 'VCI'