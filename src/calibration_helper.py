from client import ServiceClient

def main():
    freq_mhz = float(input("Frekvens i MHz: ").strip())
    freq_hz = freq_mhz * 1e6

    c = ServiceClient.from_config("config.json", "tuner2")

    result = c.call(
        {
            "cmd": "cal_add_freq",
            "f_hz": freq_hz,
            "states_csv": f"states/states_{int(freq_mhz)}MHz_adaptive.csv",
            "home_first": True
        },
        timeout_s=1800
    )

    print(result)

if __name__ == "__main__":
    main()