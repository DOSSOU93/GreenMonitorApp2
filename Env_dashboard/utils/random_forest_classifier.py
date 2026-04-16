# utils/random_forest_classifier.py

import ee
import streamlit as st
import folium
import json
import os


class RandomForestClassifier:
    """
    Classification Random Forest (version finale robuste)
    """

    def __init__(self):
        self.classes = {
            0: {'name': 'Buildings', 'color': '#FF6347'},
            1: {'name': 'Sol nu', 'color': '#D2B48C'},
            2: {'name': 'Savane', 'color': '#32CD32'},
            3: {'name': 'Eau', 'color': '#4169E1'},
            4: {'name': 'Forêt galerie', 'color': '#006400'},
            5: {'name': 'Culture', 'color': '#FFD700'},
            6: {'name': 'Forêt dense', 'color': '#228B22'}
        }

        self.palette = ['red', 'tan', 'lime', 'blue', 'darkgreen', 'yellow', 'green']
        self.bands = ['B2', 'B3', 'B4', 'B8']

        self.classifier = None
        self.classified_image = None
        self.validation_metrics = {}

    # --------------------------------------------------
    # 📡 IMAGE SATELLITE (FIX SENTINEL)
    # --------------------------------------------------
    def get_satellite_image(self, roi, start_date, end_date, cloud_threshold=10):

        try:
            collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(roi) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_threshold))

            size = collection.size().getInfo()

            if size == 0:
                st.error("❌ Aucune image trouvée")
                return None

            st.success(f"📡 {size} image(s) trouvée(s)")

            # 🔥 FIX CRITIQUE : bandes homogènes
            collection = collection.select(self.bands)

            image = collection.median().clip(roi)

            return image

        except Exception as e:
            st.error(f"Erreur image: {str(e)}")
            return None

    # --------------------------------------------------
    # 📁 ZONES D'ENTRAÎNEMENT
    # --------------------------------------------------
    def load_training_zones(self, geojson_path):

        try:
            if not os.path.exists(geojson_path):
                st.error("❌ Fichier introuvable")
                return None

            with open(geojson_path) as f:
                geojson = json.load(f)

            features = []

            for feat in geojson['features']:

                props = feat.get('properties', {})

                if 'class' not in props:
                    continue

                class_id = int(props['class'])
                geom = feat['geometry']

                if geom['type'] == 'Polygon':
                    ee_geom = ee.Geometry.Polygon(geom['coordinates'])
                elif geom['type'] == 'MultiPolygon':
                    ee_geom = ee.Geometry.MultiPolygon(geom['coordinates'])
                else:
                    continue

                features.append(ee.Feature(ee_geom, {'class': class_id}))

            if len(features) == 0:
                st.error("❌ Aucune zone valide")
                return None

            fc = ee.FeatureCollection(features)

            st.success(f"✅ {len(features)} zones d'entraînement chargées")

            return fc

        except Exception as e:
            st.error(f"Erreur chargement: {str(e)}")
            return None

    # --------------------------------------------------
    # 🤖 TRAIN + CLASSIFICATION
    # --------------------------------------------------
    def train_and_classify(self, image, training_zones, num_trees=300, scale=10, training_ratio=0.7):

        try:
            training_data = image.select(self.bands).sampleRegions(
                collection=training_zones,
                properties=['class'],
                scale=scale
            )

            size = training_data.size().getInfo()

            if size == 0:
                st.error("❌ Aucun point d'entraînement")
                return None

            st.info(f"🎯 {size} points d'entraînement")

            # Split train / validation
            with_random = training_data.randomColumn('random')

            training_set = with_random.filter(ee.Filter.lt('random', training_ratio))
            validation_set = with_random.filter(ee.Filter.gte('random', training_ratio))

            train_count = training_set.size().getInfo()
            val_count = validation_set.size().getInfo()

            st.info(f"📊 Train: {train_count} | Validation: {val_count}")

            # Entraînement
            classifier = ee.Classifier.smileRandomForest(num_trees).train(
                features=training_set,
                classProperty='class',
                inputProperties=self.bands
            )

            # Validation
            if val_count > 0:
                validated = validation_set.classify(classifier)
                confusion = validated.errorMatrix('class', 'classification')

                accuracy = confusion.accuracy().getInfo()
                kappa = confusion.kappa().getInfo()

                st.success(f"✅ Accuracy: {accuracy*100:.1f}% | Kappa: {kappa:.3f}")

                # 🔥 FIX COMPATIBILITÉ
                self.validation_metrics = {
                    "overall_accuracy": accuracy,
                    "accuracy": accuracy,
                    "kappa": kappa,
                    "training_samples": train_count,
                    "validation_samples": val_count
                }

            else:
                st.warning("⚠️ Pas de données de validation")

                # 🔥 éviter crash
                self.validation_metrics = {
                    "overall_accuracy": 0,
                    "accuracy": 0,
                    "kappa": 0,
                    "training_samples": train_count,
                    "validation_samples": 0
                }

            # Classification finale
            classified = image.select(self.bands).classify(classifier)

            self.classifier = classifier
            self.classified_image = classified

            return classified

        except Exception as e:
            st.error(f"Erreur classification: {str(e)}")
            return None

    # --------------------------------------------------
    # 🗺️ AJOUT À LA CARTE
    # --------------------------------------------------
    def add_layer(self, m):

        if self.classified_image is None:
            return m

        vis = {
            'min': 0,
            'max': 6,
            'palette': self.palette
        }

        try:
            map_id = self.classified_image.getMapId(vis)

            folium.TileLayer(
                tiles=map_id['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name='Classification RF',
                overlay=True,
                show=True
            ).add_to(m)

        except Exception as e:
            st.warning(f"Erreur affichage: {str(e)}")

        return m

    # --------------------------------------------------
    # 📊 MÉTRIQUES UI
    # --------------------------------------------------
    def show_metrics(self):

        if not self.validation_metrics:
            st.warning("Pas de métriques disponibles")
            return

        col1, col2, col3 = st.columns(3)

        with col1:
            acc = self.validation_metrics.get('overall_accuracy', 0) * 100
            st.metric("Exactitude globale", f"{acc:.1f}%")

        with col2:
            kappa = self.validation_metrics.get('kappa', 0)
            st.metric("Kappa", f"{kappa:.3f}")

        with col3:
            st.metric(
                "Échantillons",
                f"{self.validation_metrics.get('training_samples', 0)} / {self.validation_metrics.get('validation_samples', 0)}"
            )