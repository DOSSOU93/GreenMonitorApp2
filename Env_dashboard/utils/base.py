# utils/base.py
"""
Classe de base pour tous les indicateurs environnementaux
"""
from abc import ABC, abstractmethod
import streamlit as st


class BaseIndicator(ABC):
    """Classe abstraite pour les indicateurs environnementaux"""
    
    def __init__(self, name, palette_config):
        """
        Initialise l'indicateur de base
        
        Args:
            name: Nom de l'indicateur (ex: "NDVI", "NDWI", "LST")
            palette_config: Configuration de la palette de couleurs
                           Contient 'palette', 'min', 'max', 'legend' (optionnel)
        """
        self.name = name
        self.palette = palette_config.get('palette', ['#ffffff', '#000000'])
        self.min_value = palette_config.get('min', 0)
        self.max_value = palette_config.get('max', 1)
        self.legend = palette_config.get('legend', [])
        
    @abstractmethod
    def calculate(self, image, sensor_config):
        """
        Calcule l'indicateur à partir de l'image Earth Engine
        
        Args:
            image: Image Earth Engine
            sensor_config: Configuration du capteur (bandes, collection, etc.)
            
        Returns:
            Image Earth Engine avec l'indicateur calculé
        """
        pass
    
    @abstractmethod
    def interpret(self, value):
        """
        Interprète la valeur de l'indicateur
        
        Args:
            value: Valeur numérique à interpréter
            
        Returns:
            str: Interprétation textuelle avec emoji
        """
        pass
    
    def get_visualization_params(self):
        """
        Retourne les paramètres de visualisation pour Folium/EE
        
        Returns:
            dict: Paramètres min, max, palette
        """
        return {
            'min': self.min_value,
            'max': self.max_value,
            'palette': self.palette
        }
    
    def display_legend(self):
        """
        Affiche la légende de l'indicateur dans Streamlit
        Utilise la configuration de légende si disponible
        """
        if self.legend:
            cols = st.columns(len(self.legend))
            for i, item in enumerate(self.legend):
                with cols[i]:
                    st.markdown(
                        f'<div style="text-align:center;">'
                        f'<div style="background: {item["color"]}; width: 30px; height: 15px; margin: 0 auto; border: 1px solid #666; border-radius: 3px;"></div>'
                        f'<span style="font-size: 11px;">{item["label"]}</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
        else:
            # Légende par défaut si non configurée
            st.info(f"💡 Aucune légende configurée pour {self.name}")
    
    def get_stats_band_name(self):
        """
        Retourne le nom de la bande pour le calcul des statistiques
        
        Returns:
            str: Nom de la bande
        """
        return self.name