"""
Search Agent - Handles restaurant search and recommendation queries.
Performs complex queries with multiple filters and ranking.
"""

import sqlite3
from typing import List, Dict, Any
from backend.protocol.schema import Task, Artifact
from backend.config import Config

DB_PATH = Config.DB_PATH


class SearchAgent:
    """
    Specialized agent for restaurant search and discovery.
    Handles complex queries with multiple filters, price calculations, and ranking.
    """

    def __init__(self):
        self.id = "search_agent"

    def execute(self, task: Task) -> Artifact:
        """
        Executes a search task.
        Expected input_data: {"query": str, "filters": dict}
        """
        try:
            filters = task.input_data.get("filters", {})
            query_text = task.input_data.get("query", "")

            # Perform database query
            results = self._query_db(filters, query_text)

            # Separate exact location matches from nearby locations (if location filter exists)
            exact_matches, nearby_results = self._separate_by_location(results, filters)

            # Rank and sort results
            exact_matches = self._rank_results(exact_matches, filters)
            nearby_results = (
                self._rank_results(nearby_results, filters) if nearby_results else []
            )

            # Combine results: exact matches first, then nearby (if any)
            all_results = exact_matches + nearby_results

            # Add metadata to indicate which are nearby
            for result in nearby_results:
                result["_is_nearby"] = True

            return Artifact(
                task_id=task.id,
                producer_agent_id=self.id,
                status="success",
                data=all_results,
            )
        except Exception as e:
            return Artifact(
                task_id=task.id,
                producer_agent_id=self.id,
                status="failure",
                data=None,
                error_message=f"Search failed: {str(e)}",
            )

    def _query_db(
        self, filters: Dict[str, Any], query_text: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Query database with filters.
        Supports complex queries including price per person calculations.
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        query = "SELECT * FROM restaurants WHERE 1=1"
        params = []

        # Cuisine filter
        if "cuisine" in filters:
            query += " AND cuisine LIKE ?"
            params.append(f"%{filters['cuisine']}%")

        # Price range filter
        if "price_range" in filters:
            price_range = filters["price_range"]
            if isinstance(price_range, (int, float)):
                query += " AND price_range <= ?"
                params.append(int(price_range))

        # Handle budget queries (e.g., "under $200 for two")
        if "budget" in filters and "party_size" in filters:
            budget = filters.get("budget")
            party_size = filters.get("party_size", 2)
            price_per_person = budget / party_size

            # Map price per person to price_range (1-4 scale)
            # Rough mapping: $1-25=1, $26-50=2, $51-100=3, $100+=4
            if price_per_person <= 25:
                max_price_range = 1
            elif price_per_person <= 50:
                max_price_range = 2
            elif price_per_person <= 100:
                max_price_range = 3
            else:
                max_price_range = 4

            query += " AND price_range <= ?"
            params.append(max_price_range)

        # Location filter - use case-insensitive exact match
        if "location" in filters:
            location_filter = filters["location"].strip().lower()
            # Use case-insensitive exact match to ensure only matching locations are returned
            query += " AND LOWER(TRIM(location)) = ?"
            params.append(location_filter)

        # Ambiance filter
        if "ambiance" in filters:
            query += " AND ambiance LIKE ?"
            params.append(f"%{filters['ambiance']}%")

        # Minimum rating filter
        if "min_rating" in filters:
            query += " AND rating >= ?"
            params.append(float(filters["min_rating"]))

        # Capacity filter (for party size)
        if "party_size" in filters:
            party_size = filters.get("party_size")
            query += " AND capacity >= ?"
            params.append(int(party_size))

        # Text search in name or cuisine (if query_text provided)
        if query_text:
            query += " AND (name LIKE ? OR cuisine LIKE ? OR description LIKE ?)"
            search_term = f"%{query_text}%"
            params.extend([search_term, search_term, search_term])

        try:
            c.execute(query, params)
            rows = c.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            conn.close()
            raise Exception(f"Database query error: {str(e)}")

    def _separate_by_location(
        self, results: List[Dict[str, Any]], filters: Dict[str, Any]
    ) -> tuple:
        """
        Separate results into exact location matches and nearby locations.
        Returns (exact_matches, nearby_results)
        """
        if "location" not in filters or not results:
            return (results, [])

        target_location = filters["location"].strip().lower()
        exact_matches = []
        nearby_results = []

        # Define nearby locations mapping (can be expanded)
        nearby_map = {
            "downtown": ["uptown", "midtown", "east side", "west side"],
            "uptown": ["downtown", "midtown"],
            "midtown": ["downtown", "uptown"],
            "east side": ["downtown", "west side"],
            "west side": ["downtown", "east side"],
        }

        nearby_locations = nearby_map.get(target_location, [])

        for result in results:
            result_location = result.get("location", "").strip().lower()
            if result_location == target_location:
                exact_matches.append(result)
            elif result_location in nearby_locations:
                nearby_results.append(result)
            # If no location filter match, don't include (shouldn't happen with strict filter)

        return (exact_matches, nearby_results)

    def _rank_results(
        self, results: List[Dict[str, Any]], filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Rank and sort search results based on relevance.
        Considers rating, price match, and filter alignment.
        """
        if not results:
            return results

        # Calculate relevance score for each result
        scored_results = []
        for result in results:
            score = 0.0

            # Rating contributes to score (normalized to 0-1)
            rating = result.get("rating", 0)
            score += (rating / 5.0) * 0.4

            # Price range match (if specified)
            if "price_range" in filters:
                target_price = filters["price_range"]
                result_price = result.get("price_range", 0)
                # Closer match = higher score
                price_diff = abs(target_price - result_price)
                score += (1.0 - price_diff / 4.0) * 0.2

            # Ambiance match
            if "ambiance" in filters:
                target_ambiance = filters["ambiance"].lower()
                result_ambiance = result.get("ambiance", "").lower()
                if (
                    target_ambiance in result_ambiance
                    or result_ambiance in target_ambiance
                ):
                    score += 0.2

            # Location match (exact matches get higher score)
            if "location" in filters:
                target_location = filters["location"].lower().strip()
                result_location = result.get("location", "").lower().strip()
                if result_location == target_location:
                    score += 0.2  # Exact match bonus

            scored_results.append((score, result))

        # Sort by score (descending)
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # Return top results (limit to 10)
        return [result for _, result in scored_results[:10]]
