import React, { useState, useEffect } from 'react';
import { Upload, FileText, X, Search, ShieldAlert, Eye, Download, Trash2 } from 'lucide-react';
import { Button, Select, Spinner, Modal, ConfirmDialog } from '../ui';
import { toast } from 'sonner';

interface DocumentViewerProps {
    API_URL: string;
    token: string | null;
    user: any;
    onClose: () => void;
}

export default function DocumentViewer({ API_URL, token, user, onClose }: DocumentViewerProps) {
    const [file, setFile] = useState<File | null>(null);
    const [scope, setScope] = useState('general');
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

    const [documents, setDocuments] = useState<Array<{ filename: string; scope: string }>>([]);
    const [loadingDocs, setLoadingDocs] = useState(false);
    const [selectedDoc, setSelectedDoc] = useState<any>(null);
    const [loadingContent, setLoadingContent] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [pdfModalOpen, setPdfModalOpen] = useState(false);
    const [loadingPdf, setLoadingPdf] = useState(false);
    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [docToDelete, setDocToDelete] = useState<string | null>(null);
    const [deleting, setDeleting] = useState(false);

    useEffect(() => {
        fetchDocuments();
    }, [token]);

    const fetchDocuments = async () => {
        setLoadingDocs(true);
        try {
            const res = await fetch(`${API_URL}/uploaded-documents`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (res.ok) {
                const data = await res.json();
                setDocuments(data);
            }
        } catch (e) {
            console.error('Failed to fetch documents list', e);
        } finally {
            setLoadingDocs(false);
        }
    };

    const handleDocClick = async (filename: string) => {
        setLoadingContent(true);
        setSelectedDoc(null);
        try {
            const res = await fetch(`${API_URL}/uploaded-documents/${encodeURIComponent(filename)}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (res.ok) {
                const data = await res.json();
                setSelectedDoc(data);
            }
        } catch (e) {
            console.error('Failed to load document text', e);
        } finally {
            setLoadingContent(false);
        }
    };

    const handleActionPdf = async (filename: string, action: 'view' | 'download') => {
        setLoadingPdf(true);
        try {
            const res = await fetch(`${API_URL}/uploaded-documents/${encodeURIComponent(filename)}/download`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (res.ok) {
                const blob = await res.blob();
                const objectUrl = URL.createObjectURL(blob);
                if (action === 'view') {
                    setPdfUrl(objectUrl);
                    setPdfModalOpen(true);
                } else {
                    const a = document.createElement('a');
                    a.href = objectUrl;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    // Revoke after download trigger
                    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
                    toast.success(`Download started for ${filename}`);
                }
            } else {
                toast.error('This uploaded file does not have a physical PDF on the server (text chunks only). Showing content outline only.');
            }
        } catch (e) {
            console.error('Failed to get PDF file', e);
            toast.error('This uploaded file does not have a physical PDF on the server (text chunks only). Showing content outline only.');
        } finally {
            setLoadingPdf(false);
        }
    };

    const handleDeleteClick = (filename: string) => {
        setDocToDelete(filename);
        setDeleteConfirmOpen(true);
    };

    const handleConfirmDelete = async () => {
        if (!docToDelete) return;
        setDeleting(true);
        try {
            const res = await fetch(`${API_URL}/uploaded-documents/${encodeURIComponent(docToDelete)}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (res.ok) {
                toast.success(`Successfully deleted document "${docToDelete}"`);
                if (selectedDoc?.filename === docToDelete) {
                    setSelectedDoc(null);
                }
                setDeleteConfirmOpen(false);
                setDocToDelete(null);
                fetchDocuments();
            } else {
                const err = await res.json();
                toast.error(err.detail || 'Failed to delete document.');
            }
        } catch (e) {
            console.error('Delete request error', e);
            toast.error('Connection error during deletion.');
        } finally {
            setDeleting(false);
        }
    };

    const handleUploadSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file) return;

        setUploading(true);
        setUploadStatus(null);

        const formData = new FormData();
        formData.append('file', file);
        if (user.role !== 'customer') {
            formData.append('scope', scope);
        } else if (user.account_id) {
            formData.append('scope', user.account_id);
        }

        try {
            const res = await fetch(`${API_URL}/upload-document`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });

            if (res.ok) {
                const data = await res.json();
                const successMsg = `Successfully uploaded ${data.filename}. Indexing created ${data.chunks_count} chunks.`;
                setUploadStatus({
                    type: 'success',
                    msg: successMsg
                });
                toast.success(successMsg);
                setFile(null);
                // Clear input element
                const fileInput = document.getElementById('doc-file-input') as HTMLInputElement;
                if (fileInput) fileInput.value = '';
                fetchDocuments();
            } else {
                const err = await res.json();
                const errMsg = err.detail || 'Upload failed.';
                setUploadStatus({
                    type: 'error',
                    msg: errMsg
                });
                toast.error(errMsg);
            }
        } catch (err) {
            const errMsg = 'Connection error during upload.';
            setUploadStatus({
                type: 'error',
                msg: errMsg
            });
            toast.error(errMsg);
        } finally {
            setUploading(false);
        }
    };

    const filteredDocs = documents.filter(doc =>
        doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="w-full lg:w-[480px] bg-white border border-border rounded-2xl flex flex-col h-full overflow-hidden shadow-sm shrink-0">
            {/* Pane Header */}
            <div className="p-4 border-b border-border flex items-center justify-between bg-slate-50">
                <div className="flex items-center space-x-2">
                    <FileText className="h-4.5 w-4.5 text-emerald-600" />
                    <h2 className="text-xs font-black uppercase tracking-wider text-slate-800">
                        Document Policy Library
                    </h2>
                </div>
                <button
                    onClick={onClose}
                    className="text-slate-400 hover:text-slate-700 transition cursor-pointer p-0.5 rounded"
                >
                    <X className="h-4.5 w-4.5" />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {/* Document Uploader Tool */}
                <div className="p-4 bg-slate-50 border border-border rounded-xl space-y-3">
                    <h3 className="text-[11px] font-black text-slate-750 uppercase tracking-widest flex items-center gap-1.5">
                        <Upload className="h-3.5 w-3.5 text-slate-500" />
                        Upload Policy / Contract
                    </h3>
                    <form onSubmit={handleUploadSubmit} className="space-y-3">
                        <div className="border-2 border-dashed border-slate-200 hover:border-emerald-500/40 rounded-lg p-4 flex flex-col items-center justify-center bg-white transition relative">
                            <input
                                id="doc-file-input"
                                type="file"
                                accept=".pdf,.docx,.txt,.md"
                                onChange={(e) => setFile(e.target.files?.[0] || null)}
                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                required
                            />
                            <Upload className="h-6 w-6 text-slate-400 mb-2" />
                            <span className="text-xs font-bold text-slate-650 text-center">
                                {file ? file.name : 'Select PDF, DOCX, TXT, or MD'}
                            </span>
                            <span className="text-[9px] text-slate-405 block text-center mt-1">Max sized 10MB</span>
                        </div>

                        {user.role !== 'customer' ? (
                            <div>
                                <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1.5 pl-0.5">Scoping Target</label>
                                <Select
                                    value={scope}
                                    onChange={(val: string) => setScope(val)}
                                    options={[
                                        { value: 'general', label: 'General / Global (Accessible by all)' },
                                        { value: 'ACCT-001', label: 'ACCT-001 (Northstar Enterprise)' },
                                        { value: 'ACCT-002', label: 'ACCT-002 (LumenWorks Growth)' },
                                        { value: 'ACCT-003', label: 'ACCT-003 (Beacon Retail Standard)' }
                                    ]}
                                    className="text-xs font-bold bg-white"
                                />
                            </div>
                        ) : (
                            <div className="bg-slate-100 border border-slate-200 p-2.5 rounded-lg flex items-start gap-1.5">
                                <ShieldAlert className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
                                <span className="text-[10px] font-bold text-slate-600">
                                    Locked to your customer account profile scope: <span className="font-bold underline">{user.account_id}</span>.
                                </span>
                            </div>
                        )}

                        <Button
                            type="submit"
                            disabled={uploading || !file}
                            className="w-full text-xs font-black uppercase tracking-widest bg-emerald-600 hover:bg-emerald-700 text-white py-2"
                        >
                            {uploading ? 'Processing & Chunking...' : 'Upload & RAG Index'}
                        </Button>
                    </form>

                    {uploadStatus && (
                        <div className={`p-2.5 rounded-lg border text-xs font-bold ${uploadStatus.type === 'success'
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-100'
                            : 'bg-red-50 text-red-800 border-red-100'
                            }`}>
                            {uploadStatus.msg}
                        </div>
                    )}
                </div>

                {/* Directory Search & List */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between pl-1">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                            Available Documents ({filteredDocs.length})
                        </span>
                    </div>

                    <div className="relative">
                        <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search documents by directory name..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-9 pr-3 py-2 border border-border rounded-xl text-xs font-bold bg-white focus:outline-none focus:border-emerald-500 transition-colors"
                        />
                    </div>

                    {loadingDocs && (
                        <div className="py-6 flex justify-center">
                            <Spinner className="h-5 w-5 text-emerald-600 animate-spin" />
                        </div>
                    )}

                    <div className="space-y-1.5 max-h-[160px] overflow-y-auto pr-1">
                        {filteredDocs.map((doc) => (
                            <div
                                key={doc.filename}
                                className={`w-full flex items-center justify-between p-2 rounded-xl border transition text-xs font-bold ${selectedDoc?.filename === doc.filename
                                    ? 'bg-emerald-50/70 border-emerald-300 text-emerald-800'
                                    : 'bg-white border-border text-slate-700 hover:bg-slate-50'
                                    }`}
                            >
                                <button
                                    onClick={() => handleDocClick(doc.filename)}
                                    className="flex-1 flex items-center space-x-2 truncate text-left cursor-pointer p-0.5"
                                >
                                    <FileText className="h-4 w-4 shrink-0 text-slate-400" />
                                    <span className="truncate">{doc.filename}</span>
                                </button>
                                <div className="flex items-center space-x-1.5 shrink-0 ml-1">
                                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-500 uppercase tracking-wider select-none">
                                        {doc.scope}
                                    </span>
                                    {(user?.role !== 'customer' || doc.scope === user?.account_id) && (
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDeleteClick(doc.filename);
                                            }}
                                            className="text-slate-400 hover:text-red-650 hover:bg-red-50 p-1 rounded transition cursor-pointer"
                                            title="Delete Document"
                                        >
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}

                        {!loadingDocs && filteredDocs.length === 0 && (
                            <div className="py-6 text-center text-xs text-slate-400 font-bold">
                                No policy documents indexed yet.
                            </div>
                        )}
                    </div>
                </div>

                {/* Selected Document Text Outline Preview */}
                <div className="border border-border rounded-xl overflow-hidden shadow-sm">
                    <div className="bg-slate-50 p-3 border-b border-border flex items-center justify-between">
                        <span className="text-[10px] font-black text-slate-700 uppercase tracking-widest">
                            Document Preview Pane
                        </span>
                    </div>

                    {loadingContent && (
                        <div className="py-12 flex flex-col items-center justify-center text-slate-500 gap-2">
                            <Spinner className="h-6 w-6 text-emerald-650 animate-spin" />
                            <span className="text-[10px] font-bold text-slate-400 animate-pulse uppercase tracking-wider">Reading document text...</span>
                        </div>
                    )}

                    {!loadingContent && selectedDoc && (
                        <div className="p-4 space-y-4 bg-white">
                            <div className="p-3 bg-slate-50 rounded-lg border border-border space-y-2">
                                <div className="flex items-center justify-between flex-wrap gap-2">
                                    <h4 className="text-xs font-black text-slate-800 truncate">{selectedDoc.filename}</h4>
                                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${selectedDoc.authority_level === 1
                                        ? 'bg-red-50 text-red-700 border-red-200'
                                        : 'bg-emerald-50 text-emerald-700 border-emerald-250'
                                        }`}>
                                        Authority Level {selectedDoc.authority_level}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2">
                                    <span>Scope: {selectedDoc.scope}</span>
                                    <span>Date: {selectedDoc.effective_date}</span>
                                </div>
                                <div className="flex gap-2 pt-1 border-t border-slate-100">
                                    <Button
                                        onClick={() => handleActionPdf(selectedDoc.filename, 'view')}
                                        disabled={loadingPdf}
                                        variant="secondary"
                                        className="flex-1 text-[10px] font-black uppercase tracking-wider py-1.5 flex items-center justify-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 cursor-pointer"
                                    >
                                        {loadingPdf ? <Spinner className="h-3 w-3 text-slate-500 animate-spin" /> : <Eye className="h-3.5 w-3.5" />}
                                        View PDF
                                    </Button>
                                    <Button
                                        onClick={() => handleActionPdf(selectedDoc.filename, 'download')}
                                        disabled={loadingPdf}
                                        className="flex-1 text-[10px] font-black uppercase tracking-wider py-1.5 flex items-center justify-center gap-1 bg-emerald-650 hover:bg-emerald-700 text-slate-800 hover:text-white cursor-pointer"
                                    >
                                        <Download className="h-3.5 w-3.5" />
                                        Download
                                    </Button>
                                    {(user?.role !== 'customer' || selectedDoc.scope === user?.account_id) && (
                                        <Button
                                            onClick={() => handleDeleteClick(selectedDoc.filename)}
                                            className="flex-1 text-[10px] text-slate-400 font-black uppercase tracking-wider py-1.5 flex items-center justify-center gap-1 bg-red-650 hover:bg-red-700 text-slate-600 hover:text-white cursor-pointer"
                                        >
                                            <Trash2 className="h-3.5 w-3.5" />
                                            Delete
                                        </Button>
                                    )}
                                </div>
                            </div>
                            <div className="border-t border-border pt-3">
                                <div className="text-[11px] font-extrabold text-slate-400 uppercase tracking-wider mb-2">Content Outline</div>
                                <div className="h-60 overflow-y-auto p-3 bg-slate-50/50 border border-slate-100 rounded-lg text-xs leading-relaxed text-slate-750 font-medium whitespace-pre-wrap font-sans">
                                    {selectedDoc.content}
                                </div>
                            </div>
                        </div>
                    )}

                    {!loadingContent && !selectedDoc && (
                        <div className="py-16 text-center text-xs text-slate-400 font-bold bg-white">
                            Select an indexed document to view its text outline side-by-side.
                        </div>
                    )}
                </div>
            </div>
            <Modal
                open={pdfModalOpen}
                onClose={() => {
                    setPdfModalOpen(false);
                    if (pdfUrl) {
                        URL.revokeObjectURL(pdfUrl);
                        setPdfUrl(null);
                    }
                }}
                title={`Viewing Document: ${selectedDoc?.filename}`}
                className="max-w-4xl h-[90vh] flex flex-col p-4 bg-white"
            >
                <div className="flex-1 w-full h-[70vh] rounded-lg border border-border overflow-hidden mt-2 bg-slate-50">
                    {pdfUrl ? (
                        <iframe
                            src={`${pdfUrl}#toolbar=0`}
                            className="w-full h-full border-none rounded-lg"
                            title="Interactive PDF Viewer"
                        />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center text-xs font-semibold text-slate-400">
                            Loading document preview...
                        </div>
                    )}
                </div>
            </Modal>

            <ConfirmDialog
                open={deleteConfirmOpen}
                onClose={() => {
                    if (!deleting) {
                        setDeleteConfirmOpen(false);
                        setDocToDelete(null);
                    }
                }}
                onConfirm={handleConfirmDelete}
                title="Delete Document"
                description={`Are you sure you want to permanently delete "${docToDelete || ''}" from the system? This action cannot be undone and will remove it from the semantic search index.`}
                confirmLabel="Delete"
                cancelLabel="Cancel"
                variant="danger"
                loading={deleting}
            />
        </div>
    );
}
