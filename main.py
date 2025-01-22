import io
import streamlit as st
import pandas as pd
import requests
import time
import os
import json

APOLLO_API_URL_ORG = "https://api.apollo.io/api/v1/mixed_companies/search"
APOLLO_API_URL_PEOPLE = "https://api.apollo.io/v1/mixed_people/search"

DEFAULT_TITLES = ["Director of Safety", "Safety Director", "Safety Manager", "EHS Director", "HSE Manager", "Security Director", "Chief Safety Officer", "VP of Safety", "Head of Safety", "Safety Coordinator", "Environmental Health and Safety", "Occupational Safety", "Risk Manager", "Workplace Safety", "Safety"]

def get_api_key():
    """Retrieve the API key from environment variables."""
    # Comment this line if you are running the app locally
    api_key = st.secrets["APOLLO_API_KEY"]
    
    # Uncomment this line if you are running the app locally
    #api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        raise ValueError("APOLLO_API_KEY environment variable not set")
    return api_key



def search_apollo(company_domain, get_emails=False, person_titles=None):
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    
    people_payload = {
        "api_key": get_api_key(),
        "q_organization_domains": company_domain,
        "page": 1,
        "contact_email_status": "verified",
        "person_titles": person_titles or DEFAULT_TITLES,
    }   
    
    people_response = requests.post(APOLLO_API_URL_PEOPLE, headers=headers, json=people_payload)
    if people_response.status_code != 200:
        return []
        
    people = people_response.json().get('people', [])
    
    if get_emails and people:
        for i, person in enumerate(people):
            enrich_payload = {
                "api_key": get_api_key(),
                "id": person.get("id"),
                "reveal_personal_emails": True
            }
            try:
                enrich_response = requests.post("https://api.apollo.io/v1/people/match", headers=headers, json=enrich_payload)
                if enrich_response.status_code == 200:
                    enriched_person = enrich_response.json().get("person", {})
                    if enriched_person:
                        people[i]["email"] = enriched_person.get("email")
                time.sleep(0.2)
            except Exception as e:
                print(f"Error fetching email: {e}")
    
    return people

def format_contacts_for_llm(contacts):
    formatted_contacts = []
    for contact in contacts:
        contact_info = {
            "name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}",
            "title": contact.get('title', ''),
            "seniority": contact.get('seniority', ''),
            "department": contact.get('department', '')
        }
        formatted_contacts.append(contact_info)
    return json.dumps(formatted_contacts, indent=2)


def add_contact_to_row(row, cols, get_emails=False, person_titles=None):
    """Add contact information to a row using Apollo API and LLM analysis."""
    try:
        company_website = row[cols["Website"]]
        if not isinstance(company_website, str):
            return [row]
            
        try:
            domain = company_website.replace("http://", "").replace("https://", "").replace("www.", "")
            domain = domain.split('/')[0]
        except:
            return [row]
            
        contacts = search_apollo(domain, get_emails, person_titles)
        
        if not contacts:
            return [row]
            
        new_rows = []
        for contact in contacts:
            new_row = row.copy()
            new_row[cols["First Name"]] = contact.get("first_name")
            new_row[cols["Last Name"]] = contact.get("last_name")
            new_row[cols["Title"]] = contact.get("title")
            if get_emails:
                new_row[cols["Email"]] = contact.get("email")
            else:
                new_row[cols["Email"]] = "Emails not unlocked"
            new_rows.append(new_row)
        
        return new_rows
        
    except Exception as e:
        st.error(f"Error processing row: {e}")
        return [row]

def main():
    st.title("Carbyne PSAP Contact Search")
    uploaded_file = st.file_uploader("Choose an Excel file", type="xlsx")

    if uploaded_file is not None:
        sheet_name = st.text_input("Enter the sheet name you want to search", key="sheet_name_input")
        
        if not sheet_name:
            st.warning("Please enter a sheet name to proceed.")
            return
        
        try: 
            input_df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
            st.write("Columns in the uploaded sheet:", input_df.columns.tolist())

            st.write("The following titles will be used to search for contacts:")
            st.write(DEFAULT_TITLES)
            
            custom_titles = st.text_area("Enter custom titles (one per line) or leave blank to use defaults:")
            person_titles = custom_titles.split('\n') if custom_titles.strip() else DEFAULT_TITLES
            
            columns = input_df.columns.str.lower()
            
           
            lead_name_matches = columns.str.contains('organization|company|account name|lead|name')
            lead_name_col = input_df.columns[lead_name_matches].tolist()[0] if any(lead_name_matches) else None
            

            website_matches = columns.str.contains('website|url|domain|web|site')
            website_col = input_df.columns[website_matches].tolist()[0] if any(website_matches) else None
            
      
            first_name_matches = columns.str.contains('first.*name|fname|first')
            first_name_col = input_df.columns[first_name_matches].tolist()[0] if any(first_name_matches) else None
            

            last_name_matches = columns.str.contains('last.*name|lname|last|surname')
            last_name_col = input_df.columns[last_name_matches].tolist()[0] if any(last_name_matches) else None
            
   
            title_matches = columns.str.contains('title|position|job')
            title_col = input_df.columns[title_matches].tolist()[0] if any(title_matches) else None
            
       
            email_matches = columns.str.contains('email|e-mail')
            email_col = input_df.columns[email_matches].tolist()[0] if any(email_matches) else None

            lead_name_column = st.text_input("Confirm/Edit organization names column", value=lead_name_col or "", key="lead_col")
            website_column = st.text_input("Confirm/Edit website column", value=website_col or "", key="website_col")
            name1_column = st.text_input("Confirm/Edit first names column", value=first_name_col or "", key="name1_col")
            name2_column = st.text_input("Confirm/Edit last names column", value=last_name_col or "", key="name2_col")
            title_column = st.text_input("Confirm/Edit titles column", value=title_col or "", key="title_col")
            email_column = st.text_input("Confirm/Edit emails column", value=email_col or "", key="email_col")

       
            if not all([lead_name_column, website_column, name1_column, name2_column, title_column, email_column]):
                st.warning("Please confirm all column names to proceed.")
                return

            if not all(col in input_df.columns for col in [lead_name_column, website_column, name1_column, name2_column, title_column, email_column]):
                st.error("One or more column names are not present in the sheet.")
                return
            cols = {
                "Organization": lead_name_column,
                "Website": website_column,
                "First Name": name1_column,
                "Last Name": name2_column,
                "Title": title_column,
                "Email": email_column
            }

        
            st.write("\n### Please confirm the column mappings above are correct before proceeding.")
            get_emails = st.checkbox("Get emails (Note: This will use additional API credits)", value=False)
            
            if not st.button("Confirm and Process File"):
                st.info("Click the button above when you're ready to process the file.")
                return
                
            
            try:
                with st.status("Processing file...", expanded=True) as status:
                    st.write("Opening sheet...")
                    time.sleep(1)
                    st.write("Searching for employees...")
                    time.sleep(1)
                    st.write("Adding contact information...")
                    
                    new_rows = []
                    mask = input_df[name1_column].isna() & input_df[name2_column].isna() & input_df[title_column].isna() & input_df[email_column].isna()
                    
                    for idx, row in input_df.loc[mask].iterrows():
                        new_rows.extend(add_contact_to_row(row, cols, get_emails, person_titles))
                    
                    input_df = pd.concat([input_df.loc[~mask], pd.DataFrame(new_rows)], ignore_index=True)
                    
                    st.write("Contact search complete!")
                    
                 
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        input_df.to_excel(writer, index=False)
                    
           
                    st.download_button(
                        label="Download Excel file",
                        data=output.getvalue(),
                        file_name="contacts_output.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                    
                    status.update(
                        label="Contact search complete!", state="complete", expanded=False
                    )
    
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
                return

        except Exception as e:
            st.error(f"An error occurred: {e}")
            return
        

if __name__ == "__main__":
    main()