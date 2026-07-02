import { useEffect, useRef } from "react";
import { NUTRIENT_LICENSE_KEY } from "../lib/nutrientLicense.js";

export default function Viewer({ document }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    let cancelled = false;
    let NutrientViewer;

    (async () => {
      ({ default: NutrientViewer } = await import("@nutrient-sdk/viewer"));
      if (cancelled || !container || !document) return;

      NutrientViewer.unload(container);
      await NutrientViewer.load({
        container,
        document,
        useCDN: true,
        licenseKey: NUTRIENT_LICENSE_KEY,
      });
    })();

    return () => {
      cancelled = true;
      if (container) NutrientViewer?.unload(container);
    };
  }, [document]);

  return (
    <div
      ref={containerRef}
      style={{ height: "100%", width: "100%", minHeight: 0 }}
    />
  );
}
