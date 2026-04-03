import React, { useEffect, useMemo, useRef, useState } from 'react';

function menuItemsForRole(role) {
  const normalizedRole = String(role || '').toLowerCase();
  if (normalizedRole === 'staff') {
    return [
      { id: 'dashboard', label: 'Staff Dashboard' },
      { id: 'traceability', label: 'Traceability' },
      { id: 'profile', label: 'Profile' },
      { id: 'logout', label: 'Logout' },
    ];
  }
  if (normalizedRole === 'manager') {
    return [
      { id: 'simulations', label: 'Simulations' },
      { id: 'add-member', label: 'Add Member' },
      { id: 'traceability', label: 'Traceability' },
      { id: 'logout', label: 'Logout' },
    ];
  }
  return [
    { id: 'my-appointments', label: 'My Appointments' },
    { id: 'profile', label: 'Profile' },
    { id: 'logout', label: 'Logout' },
  ];
}

function roleLabel(role) {
  const normalizedRole = String(role || '').toLowerCase();
  if (normalizedRole === 'staff') {
    return 'Staff';
  }
  if (normalizedRole === 'manager') {
    return 'Manager';
  }
  return 'Patient';
}

function formatClinicFallback(value) {
  return String(value || '')
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function resolveClinicLabel(clinics, clinicId) {
  if (!clinicId) {
    return 'Not assigned';
  }
  const match = clinics.find((clinic) => clinic.id === clinicId);
  return match ? match.name : formatClinicFallback(clinicId);
}

function formatStaffClock() {
  return new Date().toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function initialsFromName(name) {
  const parts = String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) {
    return 'U';
  }
  return parts
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('');
}

export default function Navigation({
  currentPage,
  setCurrentPage,
  onHomeClick,
  currentUser,
  clinics = [],
  accountSection,
  onNavigateToAccountSection,
  onLogout,
}) {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [staffClock, setStaffClock] = useState(() => formatStaffClock());
  const userMenuRef = useRef(null);

  const normalizedRole = String(currentUser?.role || '').toLowerCase();
  const isStaffFocused = normalizedRole === 'staff';
  const menuItems = useMemo(() => menuItemsForRole(normalizedRole), [normalizedRole]);

  const displayName = String(currentUser?.full_name || 'User');
  const avatarText = useMemo(() => initialsFromName(displayName), [displayName]);
  const clinicLabel = useMemo(
    () => resolveClinicLabel(clinics, currentUser?.clinic_id),
    [clinics, currentUser?.clinic_id],
  );

  useEffect(() => {
    function handlePointer(event) {
      if (!userMenuRef.current || userMenuRef.current.contains(event.target)) {
        return;
      }
      setIsUserMenuOpen(false);
    }

    function handleEscape(event) {
      if (event.key === 'Escape') {
        setIsUserMenuOpen(false);
      }
    }

    document.addEventListener('mousedown', handlePointer);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handlePointer);
      document.removeEventListener('keydown', handleEscape);
    };
  }, []);

  useEffect(() => {
    if (!isStaffFocused) {
      return;
    }

    setStaffClock(formatStaffClock());
    const timer = window.setInterval(() => {
      setStaffClock(formatStaffClock());
    }, 30000);

    return () => window.clearInterval(timer);
  }, [isStaffFocused]);

  function renderNavLink(label, page, onClick, isActiveOverride = null) {
    const isActive = isActiveOverride ?? currentPage === page;
    return (
      <a
        href="#"
        className={`nav-link ${isActive ? 'active' : ''}`}
        onClick={(event) => {
          event.preventDefault();
          onClick();
        }}
      >
        {label}
      </a>
    );
  }

  function handleMenuItemClick(itemId) {
    setIsUserMenuOpen(false);
    if (itemId === 'logout') {
      onLogout();
      return;
    }
    if (itemId === 'traceability') {
      setCurrentPage('traceability');
      return;
    }
    onNavigateToAccountSection(itemId);
  }

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-logo" onClick={onHomeClick} style={{ cursor: 'pointer' }}>
          QIQ
        </div>

        {isStaffFocused ? (
          <div className="staff-nav-context" aria-label="Staff dashboard context">
            <div className="staff-nav-title">QueueControl Dashboard</div>
            <div className="staff-nav-meta">{clinicLabel} ({staffClock})</div>
          </div>
        ) : null}

        <ul className={`navbar-menu ${isStaffFocused ? 'staff-navbar-menu' : ''}`}>
          {!isStaffFocused ? (
            <>
              <li>{renderNavLink('Home', 'home', () => setCurrentPage('home'))}</li>
              <li>{renderNavLink('About Us', 'about', () => setCurrentPage('about'))}</li>
              <li>{renderNavLink('Team', 'team', () => setCurrentPage('team'))}</li>
              <li>{renderNavLink('Privacy & Policy', 'privacy', () => setCurrentPage('privacy'))}</li>
              <li>{renderNavLink('Contact Us', 'contact', () => setCurrentPage('contact'))}</li>
            </>
          ) : null}

          {currentUser ? (
            <li className="nav-dropdown-item nav-user-menu" ref={userMenuRef}>
              <a
                href="#"
                className={`nav-link nav-dropdown-toggle nav-user-trigger ${isUserMenuOpen ? 'active' : ''}`}
                onClick={(event) => {
                  event.preventDefault();
                  setIsUserMenuOpen((current) => !current);
                }}
              >
                <span className="nav-user-avatar" aria-hidden="true">{avatarText}</span>
                <span className="nav-user-trigger-label">{isStaffFocused ? 'Staff Account' : 'Account'}</span>
                <span className={`nav-caret ${isUserMenuOpen ? 'open' : ''}`} aria-hidden="true" />
              </a>

              {isUserMenuOpen ? (
                <div className="nav-dropdown-menu nav-user-menu-dropdown">

                  <div className="nav-user-actions">
                    {menuItems.map((item) => (
                      <a
                        key={item.id}
                        href="#"
                        className={`nav-dropdown-link ${currentPage === 'account' && accountSection === item.id ? 'active' : ''}`}
                        onClick={(event) => {
                          event.preventDefault();
                          handleMenuItemClick(item.id);
                        }}
                      >
                        {item.label}
                      </a>
                    ))}
                  </div>
                </div>
              ) : null}
            </li>
          ) : (
            <li>{renderNavLink('Login / Register', 'account', () => onNavigateToAccountSection('auth'))}</li>
          )}
        </ul>
      </div>
    </nav>
  );
}

