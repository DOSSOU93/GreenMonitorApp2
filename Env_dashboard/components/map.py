# components/map.py
import folium
import streamlit as st


def create_map(session_state, lat, lon):
    """Crée la carte principale"""
    
    if session_state.polygon_bounds:
        center_lat, center_lon, zoom = session_state.polygon_bounds
    else:
        center_lat, center_lon, zoom = lat, lon, 7
    
    m = folium.Map(
        location=[center_lat, center_lon], 
        zoom_start=zoom, 
        control_scale=True
    )
    
    # Ajouter les tuiles de fond
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='Satellite'
    ).add_to(m)
    
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap'
    ).add_to(m)
    
    # Ajouter le polygone si présent
    if session_state.polygon_coords:
        try:
            folium_coords = [[coord[0], coord[1]] for coord in session_state.polygon_coords]
            folium.Polygon(
                locations=folium_coords,
                color='red',
                weight=3,
                fill=True,
                fill_opacity=0.2,
                popup='Zone'
            ).add_to(m)
        except:
            pass
    
    return m
