from copy import deepcopy


from stock.search_manager import (
    StockSearchManager as LegacyStockSearchManager,
)


class BalancedStockSearchManager:

    def __init__(
        self,
        providers,
        per_query=5,
        max_candidates=20,
    ):

        self.providers = list(
            providers or []
        )

        self.per_query = int(
            per_query
        )

        self.max_candidates = int(
            max_candidates
        )


    # ==================================================
    # GET FIELD
    # ==================================================

    @staticmethod
    def _get_field(
        item,
        *names,
        default=None,
    ):

        if isinstance(
            item,
            dict,
        ):

            for name in names:

                if name in item:

                    return item.get(
                        name,
                        default,
                    )

            return default


        for name in names:

            if hasattr(
                item,
                name,
            ):

                return getattr(
                    item,
                    name,
                )


        return default


    # ==================================================
    # UNIQUE KEY
    # ==================================================

    def _candidate_key(
        self,
        item,
    ):

        provider = self._get_field(

            item,

            "source",

            "provider",

            default="unknown",
        )


        media_id = self._get_field(

            item,

            "id",

            "media_id",

            default=None,
        )


        if media_id is not None:

            return (
                str(provider).lower(),
                str(media_id),
            )


        download_url = self._get_field(

            item,

            "download_url",

            default="",
        )


        return (
            str(provider).lower(),
            str(download_url),
        )


    # ==================================================
    # SEARCH ONE PROVIDER
    # ==================================================

    def _search_provider(
        self,
        provider,
        scene,
    ):

        provider_name = getattr(
            provider,
            "name",
            provider.__class__.__name__,
        )


        print()
        print(
            "-" * 70
        )

        print(
            f"PROVIDER SEARCH: {provider_name}"
        )

        print(
            "-" * 70
        )


        manager = LegacyStockSearchManager(

            providers=[
                provider
            ],

            per_query=
                self.per_query,

            # Allow provider to return enough
            # candidates before global balancing.
            max_candidates=
                self.max_candidates,
        )


        try:

            provider_scene = deepcopy(
                scene
            )


            # ==================================================
            # VISUAL QUERY ORDER 58D V2
            #
            # Only first search attempt uses the interleaved:
            #
            # Exact -> Regional -> Visual -> Generic
            #
            # Retry searches must keep retry_scene queries.
            # ==================================================

            provider_search = (
                provider_scene.setdefault(
                    "search",
                    {},
                )
            )


            strategy = (
                provider_scene.get(
                    "visual_strategy",
                    {},
                )
            )


            ordered_queries = list(
                strategy.get(
                    "search_queries",
                    [],
                )
                or []
            )


            ordered_queries = [

                str(query).strip()

                for query
                in ordered_queries

                if str(
                    query
                ).strip()
            ]


            if (
                provider_search.get(
                    "visual_strategy_query_order_active"
                )
                and
                ordered_queries
            ):

                provider_search[
                    "primary_keyword"
                ] = ordered_queries[
                    0
                ]


                provider_search[
                    "keywords"
                ] = ordered_queries[
                    1:
                ]


                print(
                    "Visual query order:"
                )


                for query in ordered_queries:

                    print(
                        "  ->",
                        query,
                    )


            results = manager.search_scene(
                provider_scene
            )


        except Exception as error:

            print(
                f"[BALANCED SEARCH] "
                f"{provider_name} error: "
                f"{error}"
            )

            return []


        results = list(
            results or []
        )


        print(
            f"{provider_name} candidates:",
            len(results),
        )


        return results


    # ==================================================
    # SEARCH SCENE
    # ==================================================

    def search_scene(
        self,
        scene,
    ):

        if not self.providers:

            print(
                "[BALANCED SEARCH] "
                "No stock providers."
            )

            return []


        print()
        print(
            "=" * 70
        )

        print(
            "BALANCED MULTI-PROVIDER SEARCH"
        )

        print(
            "=" * 70
        )

        print(
            "Providers:",
            [
                getattr(
                    provider,
                    "name",
                    provider.__class__.__name__,
                )

                for provider
                in self.providers
            ],
        )

        # ==================================================
        # VISUAL PROXY POOL 58D V1
        #
        # STRICT scenes retain the original pool.
        # Proxy scenes may combine up to 20 results from
        # each of the two enabled providers -> 40 global.
        # ==================================================

        strategy = scene.get(
            "visual_strategy",
            {},
        )

        policy = strategy.get(
            "geo_policy",
            "STRICT",
        )

        visual_proxy_search = bool(
            scene.get(
                "search",
                {},
            ).get(
                "visual_proxy_search"
            )
        )


        if (
            visual_proxy_search
            and
            policy != "STRICT"
        ):

            effective_max_candidates = max(
                self.max_candidates,
                40,
            )

        else:

            effective_max_candidates = (
                self.max_candidates
            )


        print(
            "Global max candidates:",
            effective_max_candidates,
        )

        print(
            "Search policy:",
            policy,
        )


        # ==================================================
        # SEARCH EACH PROVIDER INDEPENDENTLY
        # ==================================================

        buckets = []


        for provider in self.providers:

            results = self._search_provider(

                provider,
                scene,
            )


            # Deduplicate inside provider.

            unique = []

            seen = set()


            for item in results:

                key = self._candidate_key(
                    item
                )


                if key in seen:

                    continue


                seen.add(
                    key
                )

                unique.append(
                    item
                )


            buckets.append(
                unique
            )


        # ==================================================
        # ROUND-ROBIN MERGE
        #
        # Pexels -> Pixabay -> Storyblocks -> ...
        # ==================================================

        final_results = []

        global_seen = set()

        positions = [

            0

            for _ in buckets
        ]


        while (
            len(final_results)
            < effective_max_candidates
        ):

            added_this_round = False


            for bucket_index, bucket in enumerate(
                buckets
            ):

                if (
                    len(final_results)
                    >= effective_max_candidates
                ):

                    break


                position = positions[
                    bucket_index
                ]


                # Skip duplicates until usable item.

                while (
                    position
                    < len(bucket)
                ):

                    item = bucket[
                        position
                    ]

                    position += 1


                    key = self._candidate_key(
                        item
                    )


                    if key in global_seen:

                        continue


                    global_seen.add(
                        key
                    )


                    final_results.append(
                        item
                    )


                    added_this_round = True

                    break


                positions[
                    bucket_index
                ] = position


            if not added_this_round:

                break


        # ==================================================
        # SUMMARY
        # ==================================================

        counts = {}


        for item in final_results:

            provider = self._get_field(

                item,

                "source",

                "provider",

                default="unknown",
            )


            provider = str(
                provider
                or "unknown"
            ).lower()


            counts[
                provider
            ] = (
                counts.get(
                    provider,
                    0,
                )
                + 1
            )


        print()
        print(
            "=" * 70
        )

        print(
            "BALANCED SEARCH RESULTS"
        )

        print(
            "=" * 70
        )

        print(
            "Total:",
            len(final_results),
        )

        print(
            "By provider:",
            counts,
        )


        return final_results