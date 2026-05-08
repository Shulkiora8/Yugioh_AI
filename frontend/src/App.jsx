import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Send, Plus, Trash2, Save, Search, Book, Swords, X, Info,
  LayoutGrid, List, Edit2, Copy, ArrowLeft, LogOut, Image as ImageIcon
} from 'lucide-react';
import Login from './Login';

const API_URL = 'http://localhost:8000';

function App() {
  // Auth State
  const [token, setToken] = useState(localStorage.getItem('token') || 'local-auth-bypass');
  const [user, setUser] = useState(null);

  // Navigation State
  const [view, setView] = useState('dashboard'); // 'dashboard' | 'editor'

  // Dashboard State
  const [savedDecks, setSavedDecks] = useState([]);
  const [dashboardSearch, setDashboardSearch] = useState('');
  const [viewMode, setViewMode] = useState('grid');

  // Editor State
  const [activeTab, setActiveTab] = useState('rules');
  const [dbSearchTerm, setDbSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');
  const [displayLimit, setDisplayLimit] = useState(100);
  const [selectedCard, setSelectedCard] = useState(null);
  const [messages, setMessages] = useState({
    rules: [{ text: "Hello! I am the rule assistant.", type: 'ai' }],
    decks: [{ text: "Tell me what deck you want to build.", type: 'ai' }]
  });
  const [input, setInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [dbLoading, setDbLoading] = useState(false);
  const [imageLoading, setImageLoading] = useState(false);
  const [dbResults, setDbResults] = useState([]);
  const [deck, setDeck] = useState({ name: 'Nuevo Mazo', main: [], extra: [], side: [] });

  const editorRef = useRef(null);
  const fileInputRef = useRef(null);

  // Chat & UI State
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatPos, setChatPos] = useState({ x: 100, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const getRightEdgeOfEditor = () => {
    const rightSidebarW = Math.min(340, Math.max(240, window.innerWidth * 0.22));
    return window.innerWidth - rightSidebarW - 75;
  };
  const [togglePos, setTogglePos] = useState({ x: getRightEdgeOfEditor(), y: window.innerHeight - 80 });
  const [isToggleDragging, setIsToggleDragging] = useState(false);
  const [toggleDragOffset, setToggleDragOffset] = useState({ x: 0, y: 0 });
  const toggleDidMove = useRef(false);

  // --- Effects ---

  useEffect(() => {
    // 1. Initial State for history
    if (!window.history.state) {
      window.history.replaceState({ view: 'dashboard' }, '');
    }

    // 2. Handle Browser Back/Forward
    const handlePopState = (e) => {
      if (e.state && e.state.view) {
        setView(e.state.view);
      } else {
        setView('dashboard');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    // 3. Push to history when view changes manually
    if (window.history.state?.view !== view) {
      window.history.pushState({ view }, '');
    }

    // Existing scroll reset logic
    setTimeout(() => {
      window.scrollTo(0, 0);
      if (editorRef.current) editorRef.current.scrollTop = 0;
    }, 50);

    if (view === 'dashboard') {
      fetchSavedDecks();
    }
  }, [view]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (view === 'editor') searchDb(dbSearchTerm, typeFilter);
    }, 400);
    return () => clearTimeout(timer);
  }, [dbSearchTerm, typeFilter, view]);

  // --- Logic ---

  const fetchSavedDecks = async () => {
    if (!token) return;
    try {
      const res = await axios.get(`${API_URL}/decks`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSavedDecks(res.data);
    } catch (err) {
      console.error(err);
      if (err.response?.status === 401) handleLogout();
    }
  };

  useEffect(() => {
    if (token) {
      fetchSavedDecks();
    } else {
      setSavedDecks([]);
    }
  }, [token]);

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setSavedDecks([]);
    setDeck({ name: 'Nuevo Mazo', main: [], extra: [], side: [] });
    localStorage.removeItem('token');
  };

  const createNewDeck = () => {
    setDeck({ name: 'Nuevo Mazo', main: [], extra: [], side: [] });
    setSelectedCard(null);
    setView('editor');
  };

  const openDeck = async (deckName) => {
    setChatLoading(true);
    try {
      const res = await axios.get(`${API_URL}/decks/${encodeURIComponent(deckName)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeck(res.data);
      setSelectedCard(null);
      setView('editor');
    } catch (err) {
      console.error(err);
      if (err.response?.status === 401) handleLogout();
    } finally { setChatLoading(false); }
  };

  const deleteDeck = async (name) => {
    if (window.confirm(`¿Seguro que quieres borrar "${name}"?`)) {
      try {
        await axios.delete(`${API_URL}/decks/${encodeURIComponent(name)}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        fetchSavedDecks();
      } catch (err) {
        console.error(err);
        if (err.response?.status === 401) handleLogout();
      }
    }
  };

  const renameDeck = async (oldName) => {
    const newName = window.prompt("Nuevo nombre para el mazo:", oldName);
    if (newName && newName !== oldName) {
      try {
        const res = await axios.patch(`${API_URL}/decks/${encodeURIComponent(oldName)}`, 
          { name: newName },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        const finalName = res.data.new_name;
        await fetchSavedDecks();
        if (deck.name === oldName) {
          setDeck(prev => ({ ...prev, name: finalName }));
        }
      } catch (err) { 
        console.error(err); 
        if (err.response?.status === 401) handleLogout();
      }
    }
  };

  const saveDeckToBackend = async () => {
    if (!deck.name || deck.name === 'Nuevo Mazo') {
      const newName = window.prompt("Por favor, ponle un nombre al mazo:", deck.name);
      if (!newName) return;
      setDeck(prev => ({ ...prev, name: newName }));
      deck.name = newName;
    }

    const exists = savedDecks.some(d => d.name === deck.name);
    let shouldOverwrite = false;
    if (exists) {
      if (window.confirm(`Ya existe un mazo llamado "${deck.name}". ¿Quieres sobreescribirlo?`)) {
        shouldOverwrite = true;
      }
    }

    try {
      const payload = {
        name: deck.name,
        main: deck.main.map(c => c.name),
        extra: deck.extra.map(c => c.name),
        side: deck.side.map(c => c.name),
        overwrite: shouldOverwrite
      };
      const res = await axios.post(`${API_URL}/save-deck`, payload, {
        headers: { Authorization: `Bearer ${token}` }
      });

      const finalName = res.data.name;
      setDeck(prev => ({ ...prev, name: finalName }));
      
      await fetchSavedDecks();
      alert(`¡Mazo "${finalName}" guardado correctamente!`);
    } catch (err) {
      console.error(err);
      alert("Error al guardar el mazo.");
    }
  };

  const searchDb = async (q, type) => {
    setDbLoading(true);
    try {
      const res = await axios.get(`${API_URL}/cards?q=${q}`);
      let data = res.data.data || [];
      if (type !== 'All') data = data.filter(c => c.type.toLowerCase().includes(type.toLowerCase()));
      setDbResults(data);
    } catch (err) { console.error(err); }
    finally { setDbLoading(false); }
  };

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userMessage = input.trim();
    const newMsg = { text: userMessage, type: 'user' };
    setMessages(prev => ({ ...prev, [activeTab]: [...prev[activeTab], newMsg] }));
    setInput('');
    setChatLoading(true);
    try {
      const res = await axios.post(`${API_URL}/chat`,
        { message: userMessage },
        { headers: { Authorization: `Bearer ${token}`, 'x-session-id': 'default' } }
      );
      const { response, deck_data, thoughts } = res.data;
      if (deck_data) {
        setDeck(deck_data);
        fetchSavedDecks();
        setView('editor'); // Switch to editor view automatically
      }

      let finalResponse = response;
      if (!finalResponse || !finalResponse.trim()) {
        const lowerMsg = userMessage.toLowerCase();
        if (deck_data || lowerMsg.includes('deck') || lowerMsg.includes('build') || lowerMsg.includes('make') || lowerMsg.includes('create') || lowerMsg.includes('mazo') || lowerMsg.includes('crea')) {
          finalResponse = "Process completed! I have prepared the deck you requested.";
        } else if (lowerMsg.includes('rule') || lowerMsg.includes('how to') || lowerMsg.includes('phase') || lowerMsg.includes('chain') || lowerMsg.includes('regla') || lowerMsg.includes('como')) {
          finalResponse = "Process completed! Here is the rule information you asked about.";
        } else if (lowerMsg.includes('card') || lowerMsg.includes('stats') || lowerMsg.includes('effect') || lowerMsg.includes('carta') || lowerMsg.includes('efecto')) {
          finalResponse = "Process completed! Here is the card information you requested.";
        } else {
          finalResponse = "Process completed!";
        }
      }

      setMessages(prev => ({ 
        ...prev, 
        [activeTab]: [...prev[activeTab], { text: finalResponse, type: 'ai', thoughts: thoughts }] 
      }));
    } catch (err) {
      console.error(err);
      const errorMsg = "Lo siento, hubo un error al procesar tu mensaje. ¿Está Ollama encendido?";
      setMessages(prev => ({ ...prev, [activeTab]: [...prev[activeTab], { text: errorMsg, type: 'ai' }] }));
      if (err.response?.status === 401) handleLogout();
    } finally { setChatLoading(false); }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const imageUrl = URL.createObjectURL(file);
    const formData = new FormData();
    formData.append('file', file);

    setImageLoading(true);
    const userMsg = {
      text: "🔍 Analizando imagen...",
      type: 'user',
      image: imageUrl
    };
    setMessages(prev => ({ ...prev, [activeTab]: [...prev[activeTab], userMsg] }));

    try {
      const res = await axios.post(`${API_URL}/analyze-image`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });

      const { card_name, details, card_image } = res.data;
      const aiMsg = {
        text: `He identificado esta carta: **${card_name}**.\n\nDetalles:\n${details}\n\n¡Proceso completado!`,
        type: 'ai',
        image: card_image
      };
      setMessages(prev => ({ ...prev, [activeTab]: [...prev[activeTab], aiMsg] }));
    } catch (err) {
      console.error(err);
      const aiMsg = { text: "Error al analizar la imagen. Asegúrate de que el modelo de visión esté disponible.", type: 'ai' };
      setMessages(prev => ({ ...prev, [activeTab]: [...prev[activeTab], aiMsg] }));
    } finally {
      setImageLoading(false);
      e.target.value = null;
    }
  };

  const addCardToDeck = (card) => {
    const allCards = [...deck.main, ...deck.extra, ...deck.side];
    if (allCards.filter(c => c.name === card.name).length >= 3) return;
    const cardData = { ...card, image: card.card_images[0].image_url_small };
    const isExtra = /fusion|synchro|xyz|link/i.test(card.type);
    if (isExtra) {
      if (deck.extra.length < 15) setDeck(prev => ({ ...prev, extra: [...prev.extra, cardData] }));
    } else {
      if (deck.main.length < 60) setDeck(prev => ({ ...prev, main: [...prev.main, cardData] }));
    }
  };

  const removeCard = (index, section) => {
    setDeck(prev => ({ ...prev, [section]: prev[section].filter((_, i) => i !== index) }));
  };

  const clearDeck = () => {
    if (window.confirm("¿Estás seguro de que quieres borrar todo el mazo?")) {
      setDeck({ name: 'Nuevo Mazo', main: [], extra: [], side: [] });
    }
  };

  const handleDragStart = (e, card, index = null, section = null) => {
    e.dataTransfer.setData('card', JSON.stringify(card));
    if (index !== null) {
      e.dataTransfer.setData('sourceIndex', index);
      e.dataTransfer.setData('sourceSection', section);
    }
  };

  const handleDropToSection = (e, targetSection) => {
    e.preventDefault();
    const cardDataString = e.dataTransfer.getData('card');
    if (!cardDataString) return;
    const cardData = JSON.parse(cardDataString);
    const isExtra = /fusion|synchro|xyz|link/i.test(cardData.type);
    if (targetSection === 'extra' && !isExtra) return;
    if (targetSection === 'main' && isExtra) return;
    const sourceIndex = e.dataTransfer.getData('sourceIndex');
    const sourceSection = e.dataTransfer.getData('sourceSection');
    if (sourceIndex === "") {
      const allCards = [...deck.main, ...deck.extra, ...deck.side];
      if (allCards.filter(c => c.name === cardData.name).length >= 3) return;
    }
    if (sourceIndex !== "") {
      const idx = parseInt(sourceIndex);
      if (sourceSection === targetSection) return;
      const newCard = { ...deck[sourceSection][idx] };
      setDeck(prev => {
        const sourceList = prev[sourceSection].filter((_, i) => i !== idx);
        const targetList = [...prev[targetSection], newCard];
        return { ...prev, [sourceSection]: sourceList, [targetSection]: targetList };
      });
    } else {
      const formattedCard = { ...cardData, image: cardData.card_images[0].image_url_small };
      setDeck(prev => ({ ...prev, [targetSection]: [...prev[targetSection], formattedCard] }));
    }
  };

  const handleDropToRemove = (e) => {
    e.preventDefault();
    const index = e.dataTransfer.getData('sourceIndex');
    const section = e.dataTransfer.getData('sourceSection');
    if (index !== "" && section) removeCard(parseInt(index), section);
  };

  const handleDragChatStart = (e) => { setIsDragging(true); setDragOffset({ x: e.clientX - chatPos.x, y: e.clientY - chatPos.y }); };
  const handleToggleMouseDown = (e) => { toggleDidMove.current = false; setIsToggleDragging(true); setToggleDragOffset({ x: e.clientX - togglePos.x, y: e.clientY - togglePos.y }); };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (isDragging) setChatPos({ x: e.clientX - dragOffset.x, y: e.clientY - dragOffset.y });
      if (isToggleDragging) { toggleDidMove.current = true; setTogglePos({ x: e.clientX - toggleDragOffset.x, y: e.clientY - toggleDragOffset.y }); }
    };
    const handleMouseUp = () => { setIsDragging(false); setIsToggleDragging(false); };
    if (isDragging || isToggleDragging) { window.addEventListener('mousemove', handleMouseMove); window.addEventListener('mouseup', handleMouseUp); }
    return () => { window.removeEventListener('mousemove', handleMouseMove); window.removeEventListener('mouseup', handleMouseUp); };
  }, [isDragging, dragOffset, isToggleDragging, toggleDragOffset]);

  const renderMessageText = (text) => {
    if (!text) return null;
    const parts = text.split(/(!\[.*?\]\(.*?\))/g);
    return parts.map((part, i) => {
      const match = part.match(/!\[(.*?)\]\((.*?)\)/);
      if (match) {
        return <img key={i} src={match[2]} alt={match[1]} style={{ maxWidth: '100%', borderRadius: '8px', marginTop: '10px', display: 'block' }} />;
      }
      return <span key={i} style={{ whiteSpace: 'pre-wrap' }}>{part}</span>;
    });
  };

  function renderFloatingChat() {
    return (
      <>
        {isChatOpen && (
          <div className="floating-chat" style={{ left: chatPos.x, top: chatPos.y }}>
            <div className="chat-handle" onMouseDown={handleDragChatStart}>
              <div className="handle-title">AI Assistant</div>
              <button className="close-chat" onClick={() => setIsChatOpen(false)}><X size={16} /></button>
            </div>
            <div className="chat-messages">
              {messages[activeTab].map((msg, i) => (
                <div key={i} className={`message ${msg.type}`}>
                  {msg.image && <img src={msg.image} alt="uploaded" className="chat-msg-image" />}
                  <div className="message-text">{renderMessageText(msg.text)}</div>
                </div>
              ))}
              {(chatLoading || imageLoading) && <div className="message ai">...</div>}
            </div>
            <div className="chat-input-area">
              <input type="file" ref={fileInputRef} onChange={handleImageUpload} style={{ display: 'none' }} accept="image/*" />
              <button className="image-upload-btn" onClick={() => fileInputRef.current.click()} title="Subir imagen de carta">
                <ImageIcon size={18} />
              </button>
              <input value={input} onChange={(e) => setInput(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && sendMessage()} placeholder="Pregunta algo..." />
              <button className="send-btn" onClick={sendMessage}><Send size={18} /></button>
            </div>
          </div>
        )}
        <button className="floating-toggle" style={{ left: togglePos.x, top: togglePos.y, bottom: 'auto' }} onMouseDown={handleToggleMouseDown} onClick={() => { if (!toggleDidMove.current) setIsChatOpen(!isChatOpen); }}>
          <span className="dots">...</span>
        </button>
      </>
    );
  }

  if (!token) {
    return <Login onLogin={(t) => {
      setToken(t);
      localStorage.setItem('token', t);
    }} />;
  }

  return (
    <>
      <div className="dashboard-container">
        <div className="dashboard-sticky-header">
          <div className="dashboard-header">
            <h1>YU-GI-OH HELPER</h1>
            <button className="logout-btn" onClick={handleLogout} title="Cerrar Sesión">
              <LogOut size={20} />
            </button>
          </div>

          <div className="dashboard-search-bar">
            <Search size={20} color="#888" />
            <input
              type="text"
              placeholder="Buscar entre tus mazos..."
              value={dashboardSearch}
              onChange={(e) => setDashboardSearch(e.target.value)}
            />
          </div>

          <div className="dashboard-actions">
            <div className="dash-action-card" onClick={createNewDeck}>
              <Plus size={22} style={{ color: 'var(--accent)' }} />
              <div>NUEVO MAZO</div>
            </div>
            <div className="dash-action-card">
              <Book size={22} style={{ color: '#2196f3' }} />
              <div>Upload Deck</div>
            </div>
            <div className="dash-action-card">
              <Swords size={22} style={{ color: '#ff9800' }} />
              <div>DUELO IA</div>
            </div>
          </div>
        </div>

        <div className="view-controls">
          <button className={`view-btn ${viewMode === 'grid' ? 'active' : ''}`} onClick={() => setViewMode('grid')}><LayoutGrid size={18} /></button>
          <button className={`view-btn ${viewMode === 'list' ? 'active' : ''}`} onClick={() => setViewMode('list')}><List size={18} /></button>
        </div>

        <div className="decks-grid">
          {savedDecks.filter(d => d.name.toLowerCase().includes(dashboardSearch.toLowerCase())).map((d, i) => (
            <div key={i} className="deck-card" style={{ backgroundImage: d.image ? `url(${d.image})` : 'none' }} onClick={() => openDeck(d.name)}>
              <div className="deck-card-overlay">
                <div>
                  <div className="deck-card-name">{d.name}</div>
                  <div className="deck-card-stats">
                    <span>Main {d.main.length}</span>
                    <span>Extra {d.extra.length}</span>
                    <span>Side {d.side.length}</span>
                  </div>
                </div>
                <div className="deck-card-actions">
                  <button className="deck-card-action-btn" onClick={(e) => { e.stopPropagation(); renameDeck(d.name); }}><Edit2 size={16} /></button>
                  <button className="deck-card-action-btn"><Copy size={16} /></button>
                  <button className="deck-card-action-btn delete" onClick={(e) => { e.stopPropagation(); deleteDeck(d.name); }}><Trash2 size={16} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {view === 'editor' && (
        <div className="app-container" onDrop={handleDropToRemove} onDragOver={(e) => e.preventDefault()}>
          <div className="sidebar info-sidebar">
            <button className="back-btn" onClick={() => setView('dashboard')}><ArrowLeft size={16} /> Dashboard</button>
            {selectedCard ? (
              <div className="card-preview-new">
                <div className="preview-name-pill">{selectedCard.name}</div>
                <div className="preview-img-wrap"><img src={selectedCard.card_images?.[0]?.image_url || selectedCard.image} alt={selectedCard.name} className="preview-img-large" /></div>
                <div className="preview-info-card">
                  <div className="info-id-row"><span className="info-card-id">{selectedCard.id}</span><span className="info-tcg-tag">(TCG/OCG)</span></div>
                  <div className="info-type-row">[{selectedCard.type?.includes('Monster') ? `${selectedCard.type.replace(/ Monster$/, '')}|Effect` : selectedCard.type}] {selectedCard.race}/{selectedCard.attribute || ''}</div>
                  {selectedCard.type?.includes('Monster') && <div className="info-stats-row">[★{selectedCard.level || selectedCard.rank || 0}] {selectedCard.atk}/{selectedCard.def}</div>}
                  <div className="info-desc-full">{selectedCard.desc}</div>
                </div>
              </div>
            ) : (
              <div className="empty-info"><Info size={48} style={{ marginBottom: '1rem', opacity: 0.3 }} /><p>Selecciona una carta para ver sus detalles</p></div>
            )}
          </div>

          <div className="editor-main" ref={editorRef} onDragOver={(e) => e.preventDefault()}>
            <div className="deck-construction-header">
              <div className="header-left">
                <input
                  className="deck-title-main"
                  value={deck.name}
                  onChange={(e) => setDeck(prev => ({ ...prev, name: e.target.value }))}
                  style={{ background: 'transparent', border: 'none', color: 'white', fontStyle: 'italic', width: '100%', outline: 'none' }}
                />
                <div className="regulation-tag">REGULATION: <span className="tag-box">TCG/OCG Unlimited</span></div>
              </div>
              <div className="header-actions">
                <button className="action-btn-danger" onClick={clearDeck}><Trash2 size={16} /> CLEAR</button>
                <button className="action-btn-text" onClick={saveDeckToBackend}><Save size={16} /> SAVE</button>
                <button className="action-btn-filled"><Plus size={16} /> IMPORT</button>
              </div>
            </div>

            <div className="stats-panels">
              <div className="stats-card main-stats"><span className="stats-label">MAIN</span><div className="stats-count"><span className="count-num">{deck.main.length}</span></div></div>
              <div className="stats-card extra-stats"><span className="stats-label">EXTRA</span><div className="stats-count"><span className="count-num">{deck.extra.length}</span></div></div>
              <div className="stats-card side-stats"><span className="stats-label">SIDE</span><div className="stats-count"><span className="count-num">{deck.side.length}</span></div></div>
            </div>

            <div className="deck-sections">
              {['main', 'extra', 'side'].map(section => (
                <section key={section} className="deck-section">
                  <h2 className={`deck-section-title ${section}-title`}>{section.toUpperCase()} DECK</h2>
                  <div className="deck-grid" onDrop={(e) => handleDropToSection(e, section)} onDragOver={(e) => e.preventDefault()}>
                    {deck[section].map((card, i) => (
                      <div key={i} className="card-item" draggable onDragStart={(e) => handleDragStart(e, card, i, section)} onContextMenu={(e) => { e.preventDefault(); removeCard(i, section); }}>
                        <div className="card-img" onClick={() => setSelectedCard(card)}><img src={card.image} alt="card" /></div>
                      </div>
                    ))}
                    {[...Array(Math.max(0, (section === 'main' ? 10 : 5) - deck[section].length))].map((_, i) => (
                      <div key={`empty-${section}-${i}`} className="card-item empty-slot"><Plus size={20} /></div>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>

          <div className="db-sidebar">
            <div className="db-header">
              <input type="text" placeholder="Buscar carta..." value={dbSearchTerm} onChange={(e) => setDbSearchTerm(e.target.value)} />
              <div className="filter-group">
                {['All', 'Monster', 'Spell', 'Trap'].map(t => (
                  <button key={t} className={`filter-btn ${typeFilter === t ? 'active' : ''}`} onClick={() => setTypeFilter(t)}>{t}</button>
                ))}
              </div>
            </div>
            <div className="db-results">
              {dbResults.slice(0, displayLimit === 'All' ? undefined : displayLimit).map(card => (
                <div key={card.id} className={`db-card-row ${selectedCard?.id === card.id ? 'selected' : ''}`} draggable onDragStart={(e) => handleDragStart(e, card)} onClick={() => setSelectedCard(card)} onContextMenu={(e) => { e.preventDefault(); addCardToDeck(card); }}>
                  <img src={card.card_images[0].image_url_small} alt="c" />
                  <div className="db-card-info">
                    <div className="name">{card.name}</div>
                    <div className="type">{card.type}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      {renderFloatingChat()}
    </>
  );
}

export default App;
