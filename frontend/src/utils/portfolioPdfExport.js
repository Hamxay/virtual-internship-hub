import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

/**
 * Rasterize a DOM node to a multi-page A4 PDF and trigger download.
 * @param {HTMLElement} element
 * @param {string} fileBaseName filename without extension
 */
export async function downloadElementAsPdf(element, fileBaseName) {
  if (!element) {
    throw new Error('Nothing to export');
  }

  const canvas = await html2canvas(element, {
    scale: 2,
    useCORS: true,
    allowTaint: true,
    logging: false,
    backgroundColor: '#ffffff',
    scrollX: 0,
    scrollY: -window.scrollY,
  });

  const imgData = canvas.toDataURL('image/jpeg', 0.92);
  const pdf = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
  });

  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 10;
  const imgRenderWidth = pageWidth - 2 * margin;
  const imgRenderHeight = (canvas.height * imgRenderWidth) / canvas.width;

  let heightLeft = imgRenderHeight;
  let y = margin;

  pdf.addImage(imgData, 'JPEG', margin, y, imgRenderWidth, imgRenderHeight);
  heightLeft -= pageHeight - 2 * margin;

  while (heightLeft > 0) {
    y = margin - (imgRenderHeight - heightLeft);
    pdf.addPage();
    pdf.addImage(imgData, 'JPEG', margin, y, imgRenderWidth, imgRenderHeight);
    heightLeft -= pageHeight - 2 * margin;
  }

  const safeName = (fileBaseName || 'portfolio').replace(/[^\w-]+/g, '-');
  pdf.save(`${safeName}.pdf`);
}
