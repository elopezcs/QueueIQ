import React from "react";

export default function TeamPage() {
  const team = [
    {
      name: "Dr. Sarah Johnson",
      role: "Chief Executive Officer",
      bio: "Healthcare innovator with 15+ years of experience",
      color: "#FFCCBB"
    },
    {
      name: "Michael Chen",
      role: "Chief Technology Officer",
      bio: "AI and machine learning expert",
      color: "#6EB5C0"
    },
    {
      name: "Emily Rodriguez",
      role: "Head of Operations",
      bio: "Operations specialist with expertise in healthcare systems",
      color: "#006C84"
    },
    {
      name: "David Thompson",
      role: "Lead Designer",
      bio: "UX/UI designer focused on healthcare applications",
      color: "#E2E8E4"
    },
    {
      name: "Lisa Wang",
      role: "Head of Customer Success",
      bio: "Building lasting relationships with our clients",
      color: "#FFCCBB"
    },
    {
      name: "James Martinez",
      role: "Senior Software Engineer",
      bio: "Full-stack developer with healthcare industry experience",
      color: "#6EB5C0"
    }
  ];

  return (
    <div className="page-container">
      <div className="page-header" style={{ backgroundColor: "#6EB5C0" }}>
        <h1>Our Team</h1>
        <p>Meet the talented individuals behind QueueIQ</p>
      </div>

      <section className="panel">
        <p className="team-intro">
          Our diverse team brings together expertise from healthcare, technology, and operations 
          to create innovative solutions that make a real difference in healthcare delivery.
        </p>

        <div className="team-grid">
          {team.map((member, idx) => (
            <div key={idx} className="team-card">
              <div className="team-member-image" style={{ backgroundColor: member.color }}>
                <div className="avatar-placeholder">
                  {member.name.split(" ").map(n => n[0]).join("")}
                </div>
              </div>
              <h3>{member.name}</h3>
              <p className="role">{member.role}</p>
              <p className="bio">{member.bio}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel" style={{ backgroundColor: "#f9f9f9", textAlign: "center" }}>
        <h2>Join Our Team</h2>
        <p>
          We're always looking for talented individuals to join our growing team. 
          If you're passionate about healthcare innovation, we'd love to hear from you!
        </p>
        <button className="btn">View Careers</button>
      </section>
    </div>
  );
}
