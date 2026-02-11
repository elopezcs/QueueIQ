import React from "react";

export default function Navigation({ currentPage, setCurrentPage, onHomeClick }) {
  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-logo" onClick={onHomeClick} style={{ cursor: "pointer" }}>
          QueueIQ
        </div>
        <ul className="navbar-menu">
          <li>
            <a 
              className={currentPage === "home" ? "active" : ""}
              onClick={() => setCurrentPage("home")}
            >
              Home
            </a>
          </li>
          <li>
            <a 
              className={currentPage === "about" ? "active" : ""}
              onClick={() => setCurrentPage("about")}
            >
              About Us
            </a>
          </li>
          <li>
            <a 
              className={currentPage === "team" ? "active" : ""}
              onClick={() => setCurrentPage("team")}
            >
              Team
            </a>
          </li>
          <li>
            <a 
              className={currentPage === "privacy" ? "active" : ""}
              onClick={() => setCurrentPage("privacy")}
            >
              Privacy & Policy
            </a>
          </li>
          <li>
            <a 
              className={currentPage === "contact" ? "active" : ""}
              onClick={() => setCurrentPage("contact")}
            >
              Contact Us
            </a>
          </li>
        </ul>
      </div>
    </nav>
  );
}
