from options.nse import iso_from_nse_expiry, nse_pair, parse_sides


def test_nse_pair_indices_and_equity():
    assert nse_pair("^NSEI") == ("NIFTY", "Indices")
    assert nse_pair("^NSEBANK") == ("BANKNIFTY", "Indices")
    assert nse_pair("RELIANCE.NS") == ("RELIANCE", "Equity")
    assert nse_pair("^BSESN") is None


def test_iso_from_nse_expiry():
    assert iso_from_nse_expiry("29-Sep-2026") == "2026-09-29"


def test_parse_sides_maps_oi_change():
    payload = {
        "records": {
            "underlyingValue": 23140.5,
            "data": [
                {
                    "strikePrice": 23100,
                    "CE": {
                        "lastPrice": 180,
                        "buyPrice1": 179,
                        "sellPrice1": 181,
                        "totalTradedVolume": 10,
                        "openInterest": 1000,
                        "changeinOpenInterest": 25,
                        "impliedVolatility": 12.5,
                        "change": 2,
                        "pChange": 1.1,
                        "identifier": "CE23100",
                    },
                    "PE": {
                        "lastPrice": 90,
                        "buyPrice1": 89,
                        "sellPrice1": 91,
                        "totalTradedVolume": 8,
                        "openInterest": 800,
                        "changeinOpenInterest": -10,
                        "impliedVolatility": 14,
                        "change": -1,
                        "pChange": -1.1,
                        "identifier": "PE23100",
                    },
                }
            ],
        }
    }
    calls, puts, spot = parse_sides(payload)
    assert spot == 23140.5
    assert calls[0]["oi_change"] == 25
    assert puts[0]["oi_change"] == -10
    assert calls[0]["ltp"] == 180
