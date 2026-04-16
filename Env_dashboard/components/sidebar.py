import streamlit as st
import tempfile
import os
import zipfile
import geopandas as gpd
from PIL import Image


# =========================
# 📍 POLYGONE BOUNDS
# =========================
def get_polygon_bounds(coords):
    """Calcule centre + zoom d'un polygone"""

    if coords and len(coords) > 0:

        lats = [coord[0] for coord in coords]
        lons = [coord[1] for coord in coords]

        center_lat = (max(lats) + min(lats)) / 2
        center_lon = (max(lons) + min(lons)) / 2

        lat_span = max(lats) - min(lats)
        lon_span = max(lons) - min(lons)
        max_span = max(lat_span, lon_span)

        if max_span > 5:
            zoom = 6
        elif max_span > 2:
            zoom = 7
        elif max_span > 1:
            zoom = 8
        elif max_span > 0.5:
            zoom = 9
        elif max_span > 0.2:
            zoom = 10
        elif max_span > 0.1:
            zoom = 11
        else:
            zoom = 12

        return center_lat, center_lon, zoom

    return None, None, 10


# =========================
# 🧭 SIDEBAR
# =========================
def create_sidebar(COLOR_PALETTES, INDICATORS, YEARS, MONTHS, SENSORS_BY_INDICATOR, LOGO_PATH):

    with st.sidebar:

        # =========================
        # 🖼️ LOGO PREMIUM HEADER
        # =========================
        if os.path.exists(LOGO_PATH):
            logo = Image.open(LOGO_PATH)

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(logo, width=180)

            st.markdown(
                """
                <div style="
                    text-align:center;
                    font-size:18px;
                    font-weight:600;
                    margin-top:-10px;
                    margin-bottom:15px;
                    color:#2E7D32;
                ">
                    🌿 Vegetation Monitoring System
                </div>
                """,
                unsafe_allow_html=True
            )

        else:
            st.markdown(
                """
                <div style="text-align:center; font-size:48px;">🌿</div>
                <div style="text-align:center; font-weight:600; color:#2E7D32;">
                    Vegetation Monitoring System
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

        # =========================
        # 📍 COORDONNÉES
        # =========================
        st.markdown("**📍 Coordonnées**")
        col1, col2 = st.columns(2)

        with col1:
            lat = st.number_input("Latitude", value=6.5, format="%.4f", key="lat")

        with col2:
            lon = st.number_input("Longitude", value=1.2, format="%.4f", key="lon")

        st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)

        # =========================
        # 📁 SHAPEFILE
        # =========================
        st.markdown("**📁 Zone d'étude**")

        uploaded_zip = st.file_uploader("Shapefile (ZIP)", type=['zip'], key="shp")

        if uploaded_zip:

            try:
                with tempfile.TemporaryDirectory() as tmpdir:

                    zip_path = os.path.join(tmpdir, "shapefile.zip")

                    with open(zip_path, 'wb') as f:
                        f.write(uploaded_zip.getbuffer())

                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(tmpdir)

                    shp_files = [
                        os.path.join(root, f)
                        for root, dirs, files in os.walk(tmpdir)
                        for f in files if f.endswith('.shp')
                    ]

                    if shp_files:
                        gdf = gpd.read_file(shp_files[0])

                        if len(gdf) > 0 and gdf.geometry.iloc[0].geom_type == 'Polygon':

                            coords = list(gdf.geometry.iloc[0].exterior.coords)

                            coords_latlon = [[coord[1], coord[0]] for coord in coords]

                            st.session_state.polygon_coords = coords_latlon
                            st.session_state.shapefile_name = os.path.basename(shp_files[0])

                            center = get_polygon_bounds(coords_latlon)
                            st.session_state.polygon_bounds = center

                            st.success(f"✅ Chargé: {st.session_state.shapefile_name}")

            except Exception as e:
                st.error(f"Erreur shapefile: {e}")

        # =========================
        # 🗑️ RESET
        # =========================
        if st.session_state.get('polygon_coords'):

            if st.button("🗑️ Effacer zone", use_container_width=True):

                keys_to_reset = [
                    'polygon_coords', 'shapefile_name', 'polygon_bounds',
                    'ee_polygon', 'analysis_results', 'analysis_done',
                    'show_results', 'result_image', 'geotiff_url',
                    'timeseries_data', 'seasonal_data'
                ]

                for key in keys_to_reset:
                    st.session_state[key] = None

                st.session_state.analysis_done = False
                st.session_state.show_results = False

                st.rerun()

        st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)

        # =========================
        # 📊 INDICATEUR + CAPTEUR
        # =========================
        with st.expander("📊 Indicateur", expanded=True):

            selected_indicator = st.selectbox(
                "Indicateur",
                INDICATORS,
                index=INDICATORS.index(
                    st.session_state.get('selected_indicator', INDICATORS[0])
                ) if st.session_state.get('selected_indicator') in INDICATORS else 0,
                key="indicator"
            )

            st.session_state.selected_indicator = selected_indicator

            available_sensors = list(SENSORS_BY_INDICATOR[selected_indicator].keys())

            selected_sensor_name = st.radio(
                "Capteur",
                available_sensors,
                index=0,
                key="sensor"
            )

            st.session_state.selected_sensor = selected_sensor_name

            sensor_config = SENSORS_BY_INDICATOR[selected_indicator][selected_sensor_name]

        # =========================
        # 📅 PÉRIODE
        # =========================
        with st.expander("📅 Période", expanded=True):

            analysis_type = st.radio(
                "Type d'analyse",
                ["Mensuelle", "Annuelle"],
                horizontal=True,
                key="type"
            )

            if analysis_type == "Mensuelle":

                col1, col2 = st.columns(2)

                with col1:
                    year = st.selectbox(
                        "Année",
                        YEARS,
                        index=YEARS.index(2023) if 2023 in YEARS else 0,
                        key="y"
                    )

                with col2:
                    month_name = st.selectbox(
                        "Mois",
                        MONTHS,
                        index=5,
                        key="m"
                    )

                    month = MONTHS.index(month_name) + 1

            else:
                year = st.selectbox(
                    "Année",
                    YEARS,
                    index=YEARS.index(2023) if 2023 in YEARS else 0,
                    key="y2"
                )
                month = None

        # =========================
        # 📊 COMPARAISON
        # =========================
        enable_comparison = st.checkbox("📊 Comparer avec une autre année", key="comp")

        compare_year = None

        if enable_comparison:
            compare_year = st.selectbox(
                "Année de référence",
                YEARS,
                index=YEARS.index(2020) if 2020 in YEARS else 0,
                key="comp_y"
            )

        # =========================
        # ⚙️ OPTIONS
        # =========================
        with st.expander("⚙️ Options", expanded=False):

            resolution = st.select_slider(
                "Résolution",
                options=["Basse (1000m)", "Moyenne (500m)", "Haute (100m)"],
                value="Moyenne (500m)",
                key="res"
            )

            scale_map = {
                "Basse (1000m)": 1000,
                "Moyenne (500m)": 500,
                "Haute (100m)": 100
            }

            analysis_scale = scale_map[resolution]

            cloud_threshold = st.slider(
                "Seuil nuages (%)",
                0, 100, 20, 5,
                help="Pourcentage maximum de nuages accepté"
            )

            export_geotiff = st.checkbox("🗺️ Export GeoTIFF")

            show_timeseries = st.checkbox(
                "📈 Série temporelle",
                value=False
            )

            if show_timeseries:
                col1, col2 = st.columns(2)

                with col1:
                    ts_start = st.number_input("Début", 2000, 2025, 2017)

                with col2:
                    ts_end = st.number_input("Fin", 2001, 2026, 2024)

            else:
                ts_start, ts_end = None, None

            show_seasonal = st.checkbox(
                "📊 Saisonnière",
                value=False
            )

        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

        # =========================
        # 🚀 RUN
        # =========================
        submit = st.button("🚀 Lancer l'analyse", use_container_width=True)

    return {
        "lat": lat,
        "lon": lon,
        "selected_indicator": selected_indicator,
        "selected_sensor": selected_sensor_name,
        "sensor_config": sensor_config,
        "analysis_type": analysis_type,
        "year": year,
        "month": month,
        "enable_comparison": enable_comparison,
        "compare_year": compare_year,
        "analysis_scale": analysis_scale,
        "cloud_threshold": cloud_threshold,
        "export_geotiff": export_geotiff,
        "show_timeseries": show_timeseries,
        "ts_start": ts_start,
        "ts_end": ts_end,
        "show_seasonal": show_seasonal,
        "submit": submit
    }