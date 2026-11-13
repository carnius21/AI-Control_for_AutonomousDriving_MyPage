"""Same frozen protocol as route04; only route and result directory differ."""
from utils import train_navigation_route04 as runner
runner.ROUTE='route_14'
runner.DEST=runner.ROOT/'results/navigation_route14_v1'
if __name__=='__main__':runner.main()
