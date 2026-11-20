// Turns Mermaid text into a PNG (base64) so the Word document can include the diagram as a picture.

function toSvgElement(svg: string): Element | null {
  // Mermaid output is usually valid XML; if not, read it leniently as HTML and take the <svg>.
  const strict = new DOMParser().parseFromString(svg, "image/svg+xml");
  if (!strict.querySelector("parsererror")) return strict.documentElement;
  return new DOMParser().parseFromString(svg, "text/html").querySelector("svg");
}

export async function mermaidToPngBase64(text: string): Promise<string | null> {
  try {
    const mermaid = (await import("mermaid")).default;
    // Plain SVG text labels (no HTML): browsers only draw such SVGs onto a canvas.
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "neutral",
      htmlLabels: false,
      flowchart: { htmlLabels: false },
    });
    const plainText = text.replace(/<\/?small>/g, ""); // small-text tags only work in HTML labels
    const { svg } = await mermaid.render(`export-${Date.now()}`, plainText);
    // Restore normal settings for the on-screen diagrams.
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral", htmlLabels: true, flowchart: { htmlLabels: true } });

    const element = toSvgElement(svg);
    if (!element) return null;
    const viewBox = (element.getAttribute("viewBox") ?? "0 0 800 600").split(/[\s,]+/).map(Number);
    const [width, height] = [Math.ceil(viewBox[2]) || 800, Math.ceil(viewBox[3]) || 600];
    element.setAttribute("width", String(width));
    element.setAttribute("height", String(height));
    element.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    const svgText = new XMLSerializer().serializeToString(element);

    const img = new Image();
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgText);
    await img.decode();

    const scale = 2; // sharper picture in Word
    const canvas = document.createElement("canvas");
    canvas.width = width * scale;
    canvas.height = height * scale;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/png").split(",")[1];
  } catch (err) {
    console.warn("Diagram picture could not be created:", err);
    return null; // the document is still created, just without the picture
  }
}
