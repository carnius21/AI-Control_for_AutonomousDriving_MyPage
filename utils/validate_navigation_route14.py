"""Reuse S0 checks with route14 default environment and separate evidence."""
from utils.train_navigation_route14 import runner
from utils import validate_navigation_observation as validation
validation.DEST=runner.DEST
if __name__=='__main__':validation.main()
