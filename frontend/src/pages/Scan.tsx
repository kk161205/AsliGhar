import { Image, IndianRupee, MapPin } from "lucide-react";
import Nav from "../components/Nav";
import ScanFlow from "../components/ScanFlow";

export default function Scan() {
  return (
    <>
      <Nav />
      <main className="page page--scan">
        <div className="scan-layout">
          <div className="scan-layout__main">
            <h1>Check a listing</h1>
            <p className="scan-layout__lede">
              Add the photos and details as they appear in the listing. We cross-check them
              against public listings, maps, and price data — nothing here gets sent anywhere
              until you submit.
            </p>
            <ScanFlow />
          </div>

          <aside className="scan-layout__aside" aria-label="What we check">
            <h2>What we check</h2>
            <ul className="check-list">
              <li>
                <Image aria-hidden="true" size={20} strokeWidth={1.75} />
                <div>
                  <p className="check-list__title">Image reuse</p>
                  <p className="check-list__body">
                    Whether these exact photos turn up elsewhere, at a different price or city.
                  </p>
                </div>
              </li>
              <li>
                <MapPin aria-hidden="true" size={20} strokeWidth={1.75} />
                <div>
                  <p className="check-list__title">Address plausibility</p>
                  <p className="check-list__body">
                    Whether the stated address resolves to a real, sensible location.
                  </p>
                </div>
              </li>
              <li>
                <IndianRupee aria-hidden="true" size={20} strokeWidth={1.75} />
                <div>
                  <p className="check-list__title">Price sanity</p>
                  <p className="check-list__body">
                    How far the rent sits from comparable listings in that locality.
                  </p>
                </div>
              </li>
            </ul>
          </aside>
        </div>
      </main>
    </>
  );
}
