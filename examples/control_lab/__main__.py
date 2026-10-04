"""python -m examples.control_lab --port 8876"""
import argparse
import uvicorn
from .app import create_app


def main():
    parser = argparse.ArgumentParser(description='Run the optional local Strata Control Lab')
    parser.add_argument('--port', type=int, default=8876)
    args = parser.parse_args()
    # This demo uses server-side Strata credentials; keep its UI on loopback.
    uvicorn.run(create_app(), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
