"""
Indicateur LST (Land Surface Temperature)
VERSION ROBUSTE - réduction des trous (cloud gaps)
Landsat 8/9 Collection 2 Level-2
"""

import ee
import streamlit as st
from .base import BaseIndicator


class LSTIndicator(BaseIndicator):

    def __init__(self, palette_config):
        super().__init__("LST", palette_config)

    # =========================
    # 📅 SMART WINDOW (IMPORTANT)
    # =========================
    def build_window(self, year, month):
        """
        Étend automatiquement la période pour réduire les trous
        """

        # période élargie automatique (3 mois total)
        start_month = max(month - 1, 1)
        end_month = min(month + 1, 12)

        start = f"{year}-{start_month:02d}-01"

        # fin du mois (simplifié robuste)
        end = f"{year}-{end_month:02d}-30"

        return start, end

    # =========================
    # 🌡️ CALCUL LST
    # =========================
    def calculate(self, collection, sensor_config, year=None, month=None):
        """
        LST robuste avec réduction des trous
        """

        try:

            if collection is None:
                st.warning("Aucune collection")
                return None

            if collection.size().getInfo() == 0:
                st.warning("Aucune image disponible")
                return None

            # =========================
            # 📅 ÉTENDRE LA PÉRIODE
            # =========================
            if year is not None and month is not None:
                start, end = self.build_window(year, month)

                collection = collection.filterDate(start, end)

            # =========================
            # ☁️ MASQUE NUAGES (MODÉRÉ)
            # =========================
            def mask_clouds(img):

                if 'QA_PIXEL' not in img.bandNames().getInfo():
                    return img

                qa = img.select("QA_PIXEL")

                cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)

                return img.updateMask(cloud_mask)

            collection = collection.map(mask_clouds)

            # =========================
            # 🌡️ CONVERSION LST
            # =========================
            def to_lst(img):

                lst = img.select("ST_B10") \
                    .multiply(0.00341802) \
                    .add(149.0) \
                    .subtract(273.15) \
                    .rename("LST")

                return lst.copyProperties(img, ["system:time_start"])

            lst_collection = collection.map(to_lst)

            # =========================
            # 🧠 COMPOSITE ROBUSTE
            # =========================
            median = lst_collection.median()

            try:
                quality = lst_collection.qualityMosaic("LST")
            except:
                quality = median

            # fusion intelligente anti-trous
            final = median.unmask(quality)

            return final.rename("LST")

        except Exception as e:
            st.error(f"Erreur LST: {e}")
            return None

    # =========================
    # 🌡️ INTERPRÉTATION
    # =========================
    def interpret(self, value):

        if value is None:
            return "Pas de données", "secondary"

        if value > 45:
            return "Chaleur extrême 🔥", "error"
        elif value > 38:
            return "Très chaud 🌡️", "error"
        elif value > 32:
            return "Chaud ☀️", "warning"
        elif value > 25:
            return "Tempéré 🌤️", "info"
        elif value > 15:
            return "Frais 🌥️", "info"
        else:
            return "Froid ❄️", "success"

    # =========================
    # 📊 STATISTIQUES
    # =========================
    def get_stats(self, lst_image, region, scale=30):

        try:
            stats = lst_image.reduceRegion(
                reducer=ee.Reducer.mean()
                .combine(ee.Reducer.minMax(), sharedInputs=True),
                geometry=region,
                scale=scale,
                bestEffort=True,
                maxPixels=1e9
            ).getInfo()

            return {
                "mean": stats.get("LST_mean"),
                "min": stats.get("LST_min"),
                "max": stats.get("LST_max")
            }

        except Exception as e:
            st.error(f"Erreur stats LST: {e}")
            return None

    # =========================
    # 📛 NOM BANDE
    # =========================
    def get_stats_band_name(self):
        return "LST"