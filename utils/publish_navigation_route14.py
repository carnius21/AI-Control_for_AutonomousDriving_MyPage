"""Publish only the route14 runs, using the route04 validation protocol."""
from utils import publish_navigation_route04 as publisher
publisher.OUT=publisher.ROOT/'results/navigation_route14_v1'
publisher.DOC=publisher.ROOT/'docs/ic-navigation-route14-results.md'
publisher.ROUTE_LABEL='14'
if __name__=='__main__':publisher.main()
