import React from "react";

export default function TeamPage() {
  const team = [
    {
      name: "Edwin Lopez Castañeda",
      role: "AI & Software Developer",
      bio: "Student at Conestoga College. Passionate about building AI-driven healthcare solutions.",
      color: "var(--color-peach)",
      email: "elopezcastaneda@conestogac.on.ca",
      phone: "+1 (555) 123-4567",
      linkedin: "#",
      github: "#"
    },
    {
      name: "Jatinder Pal Singh",
      role: "AI & Software Developer",
      bio: "Student at Conestoga College. Focused on machine learning and backend architecture.",
      color: "var(--color-water)",
      email: "jsingh@conestogac.on.ca",
      phone: "+1 (555) 234-5678",
      linkedin: "#",
      github: "#"
    },
    {
      name: "Rohit Krishnamurthy Iyer",
      role: "AI & Software Developer",
      bio: "Student at Conestoga College. Specializing in full-stack development and data engineering.",
      color: "var(--color-azure)",
      email: "riyer@conestogac.on.ca",
      phone: "+1 (555) 345-6789",
      linkedin: "#",
      github: "#"
    },
    {
      name: "Mostafa Allahmoradi",
      role: "AI & Software Developer",
      bio: "Student at Conestoga College. Expert in predictive modeling and system integration.",
      color: "var(--color-air)",
      email: "mallahmoradi@conestogac.on.ca",
      phone: "+1 (555) 456-7890",
      linkedin: "#",
      github: "#"
    }
  ];

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Our Team</h1>
        <p>Meet the creators of the QueueIQ AI project</p>
      </div>

      <section className="panel">
        <p className="team-intro">
          We are a team of dedicated students from Conestoga College who built this AI-based project 
          to revolutionize healthcare queue management and improve patient experiences.
        </p>

        <div className="team-grid">
          {team.map((member, idx) => (
            <div key={idx} className="team-card">
              <div className="team-member-image" style={{ backgroundColor: member.color }}>
                <div className="avatar-placeholder">
                  {member.name.split(" ").slice(0, 2).map(n => n[0]).join("")}
                </div>
              </div>
              <h3>{member.name}</h3>
              <p className="role">{member.role}</p>
              <p className="bio">{member.bio}</p>
              
              <div className="team-contact">
                <div>📧 <a href={`mailto:${member.email}`}>{member.email}</a></div>
                <div>📱 <a href={`tel:${member.phone}`}>{member.phone}</a></div>
              </div>

              <div className="team-social">
                <a href={member.linkedin} target="_blank" rel="noopener noreferrer">LinkedIn</a>
                <a href={member.github} target="_blank" rel="noopener noreferrer">GitHub</a>
                <a href="#" target="_blank" rel="noopener noreferrer">Portfolio</a>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
