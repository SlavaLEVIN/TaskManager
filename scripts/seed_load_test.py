import sys
from seed_data import main

if __name__ == "__main__":
    sys.argv.append("--load")
    main()
