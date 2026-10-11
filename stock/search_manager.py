class StockSearchManager:

    def __init__(
        self,
        providers,
        per_query=8,
        max_candidates=30
    ):

        self.providers = providers

        self.per_query = per_query

        self.max_candidates = (
            max_candidates
        )


    # ==================================================
    # SEARCH SCENE
    # ==================================================

    def search_scene(
        self,
        scene
    ):

        search_data = scene[
            "search"
        ]

        stock_data = scene[
            "stock"
        ]


        preferred_type = (
            stock_data.get(
                "preferred_type",
                "video"
            )
        )


        # Manifest hiện tại chưa lưu media,
        # nên mặc định video.

        if preferred_type not in (
            "video",
            "image",
            "either"
        ):

            preferred_type = "video"


        queries = self._build_queries(
            search_data
        )


        print(
            "Search queries:"
        )

        for query in queries:

            print(
                "  -",
                query
            )


        candidates = []

        seen = set()

        searches = []


        # ==================================================
        # PROVIDERS
        # ==================================================

        for provider in self.providers:

            for query in queries:

                if (
                    len(candidates)
                    >= self.max_candidates
                ):

                    break


                print(
                    f"Searching "
                    f"{provider.name}: "
                    f"{query}"
                )


                try:

                    results = (
                        self._provider_search(
                            provider,
                            query,
                            preferred_type
                        )
                    )


                except Exception as error:

                    print(
                        f"  Provider error: "
                        f"{error}"
                    )

                    searches.append({

                        "provider": (
                            provider.name
                        ),

                        "query": query,

                        "status": "error",

                        "error": str(
                            error
                        ),

                        "results": 0
                    })

                    continue


                searches.append({

                    "provider": (
                        provider.name
                    ),

                    "query": query,

                    "status": "success",

                    "results": len(
                        results
                    )
                })


                print(
                    "  Results:",
                    len(results)
                )


                # ==========================================
                # DEDUPLICATE
                # ==========================================

                for item in results:

                    unique_key = (

                        item.provider,

                        item.media_type,

                        item.media_id
                    )


                    if unique_key in seen:

                        continue


                    seen.add(
                        unique_key
                    )


                    candidate = (
                        item.to_dict()
                    )


                    candidate[
                        "matched_query"
                    ] = query


                    candidates.append(
                        candidate
                    )


                    if (
                        len(candidates)
                        >= self.max_candidates
                    ):

                        break


        # ==================================================
        # UPDATE STOCK DATA
        # ==================================================

        stock_data[
            "candidates"
        ] = candidates


        stock_data[
            "searches"
        ] = searches


        if candidates:

            stock_data[
                "status"
            ] = "searched"

        else:

            stock_data[
                "status"
            ] = "no_results"


        return candidates


    # ==================================================
    # BUILD QUERY LIST
    # ==================================================

    def _build_queries(
        self,
        search_data
    ):

        queries = []


        primary = (
            search_data
            .get(
                "primary_keyword",
                ""
            )
            .strip()
        )


        if primary:

            queries.append(
                primary
            )


        for query in search_data.get(
            "keywords",
            []
        ):

            query = query.strip()


            if (
                query
                and query not in queries
            ):

                queries.append(
                    query
                )


        return queries


    # ==================================================
    # PROVIDER SEARCH
    # ==================================================

    def _provider_search(
        self,
        provider,
        query,
        preferred_type
    ):

        if preferred_type == "image":

            return provider.search_images(
                query=query,
                per_page=self.per_query
            )


        if preferred_type == "either":

            videos = (
                provider.search_videos(
                    query=query,
                    per_page=self.per_query
                )
            )


            images = (
                provider.search_images(
                    query=query,
                    per_page=self.per_query
                )
            )


            return (
                videos
                +
                images
            )


        return provider.search_videos(
            query=query,
            per_page=self.per_query
        )