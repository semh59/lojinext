"""
Polyline decoding utility for Google Encoded Polyline Algorithm Format.
Used to decode geometry strings from OpenRouteService without external dependencies.
"""

from typing import List, Tuple


class PolylineDecoder:
    @staticmethod
    def decode(polyline_str: str) -> List[Tuple[float, float]]:
        """
        Decodes a polyline string into a list of (latitude, longitude) tuples.

        Args:
            polyline_str: Encoded polyline string

        Returns:
            List of (latitude, longitude)
        """
        points = []
        index = 0
        len_str = len(polyline_str)
        lat = 0
        lng = 0

        while index < len_str:
            shift = 0
            result = 0

            # Decode Latitude
            while True:
                if index >= len_str:
                    break
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break

            dlat = ~(result >> 1) if (result & 1) else (result >> 1)
            lat += dlat

            shift = 0
            result = 0

            # Decode Longitude
            while True:
                if index >= len_str:
                    break
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break

            dlng = ~(result >> 1) if (result & 1) else (result >> 1)
            lng += dlng

            points.append((lat / 1e5, lng / 1e5))

        return points
