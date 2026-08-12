import { useEffect, useRef, useState } from 'react';
import {
    CheckCircle2,
    Download,
    FileText,
    Loader2,
} from 'lucide-react';

export function PdfDownloader({
    pdfUrl,
    fileName = 'document.pdf',
    title = 'Download PDF',
    description = 'Download your document securely as a PDF file.',
}) {
    const [status, setStatus] = useState('idle');
    const [error, setError] = useState('');
    const resetTimer = useRef(null);

    useEffect(() => () => {
        if (resetTimer.current)
            window.clearTimeout(resetTimer.current);
    }, []);

    const handleDownload = async () => {
        if (!pdfUrl) {
            setStatus('error');
            setError('PDF preview is not ready yet.');
            return;
        }
        try {
            setStatus('loading');
            setError('');
            const response = await fetch(pdfUrl, {
                credentials: 'include',
            });
            if (!response.ok)
                throw new Error('Unable to download the PDF.');
            const blob = await response.blob();
            if (!blob.type.toLowerCase().includes('pdf'))
                throw new Error('The downloaded file is not a valid PDF.');

            const downloadUrl = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = fileName;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(downloadUrl);

            setStatus('success');
            resetTimer.current = window.setTimeout(() => {
                setStatus('idle');
                resetTimer.current = null;
            }, 2500);
        }
        catch (downloadError) {
            setStatus('error');
            setError(
                downloadError instanceof Error
                    ? downloadError.message
                    : 'Download failed.'
            );
        }
    };

    return <section className="pdf-downloader" aria-labelledby="pdf-download-title">
      <div className="pdf-downloader__heading">
        <span className="pdf-downloader__file-icon" aria-hidden="true"><FileText size={25}/></span>
        <div><h3 id="pdf-download-title">{title}</h3><p>{description}</p></div>
      </div>
      <div className="pdf-downloader__file">
        <div><strong title={fileName}>{fileName}</strong><span>PDF document</span></div>
        <span className="pdf-downloader__extension">.PDF</span>
      </div>
      {error && <div className="pdf-downloader__error" role="alert">{error}</div>}
      <button className="button button--primary pdf-downloader__button" type="button" disabled={status === 'loading'} onClick={() => void handleDownload()}>
        {status === 'loading' && <><Loader2 className="pdf-downloader__spinner" size={19} aria-hidden="true"/>Downloading…</>}
        {status === 'success' && <><CheckCircle2 size={19} aria-hidden="true"/>Downloaded</>}
        {(status === 'idle' || status === 'error') && <><Download size={19} aria-hidden="true"/>Download PDF</>}
      </button>
    </section>;
}
