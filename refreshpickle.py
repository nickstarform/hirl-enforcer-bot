import pickle
import argparse
import importlib.util


class Config:
    def __init__(self, inp):
        self.base = dir(self)
        if isinstance(inp, dict):
            for key, value in inp.items():
                setattr(self, key, value)
        else:
            for key in dir(inp):
                if '__' not in key and key not in self.base:
                    setattr(self, key, getattr(inp, key))

    def to_dict(self):
        ret = {}
        for key in dir(self):
            if '__' not in key and key not in self.base:
                val = getattr(self, key)
                ret[key] = val if not isinstance(val, set) else list(val)
        return ret


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Startup the bot')
    parser.add_argument('--input', dest='input', type=str, help='name of the config file')
    args = parser.parse_args()
    config = importlib.import_module(args.input)
    config = Config(config).to_dict()
    with open(f'{args.input}.pickle', 'wb') as f:
        pickle.dump(config, f)
    print(f'Pickle refreshed')
