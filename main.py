import io
import streamlit as st
import pandas as pd
import requests
import time
import os
import json
import openai

# openai.api_key = os.getenv("OPENAI_API_KEY") 

openai.api_key = st.secrets["OPENAI_API_KEY"] 

APOLLO_API_URL_ORG = "https://api.apollo.io/api/v1/mixed_companies/search"
APOLLO_API_URL_PEOPLE = "https://api.apollo.io/v1/mixed_people/search"

def get_api_key():
    """Retrieve the API key from environment variables."""
    #api_key = os.getenv("APOLLO_API_KEY")
    api_key = st.secrets["APOLLO_API_KEY"]
    if not api_key:
        raise ValueError("APOLLO_API_KEY environment variable not set")
    return api_key



#     return row_dict
def search_apollo(company_domain, get_emails=False):
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    
    people_payload = {
        "api_key": get_api_key(),
        "q_organization_domains": company_domain,
        "page": 1,
        "contact_email_status": "verified",
        "person_titles": ["Director of Safety", "Safety Director", "Safety Manager", "EHS Director", "HSE Manager", "Security Director", "Chief Safety Officer", "VP of Safety", "Head of Safety", "Safety Coordinator", "Environmental Health and Safety", "Occupational Safety", "Risk Manager", "Workplace Safety", "Director", "VP", "Safety"],
    }   
    
    people_response = requests.post(APOLLO_API_URL_PEOPLE, headers=headers, json=people_payload)
    if people_response.status_code != 200:
        return []
        
    people = people_response.json().get('people', [])
    
    if get_emails and people:
        # Fetch email for the first person
        enrich_payload = {
            "api_key": get_api_key(),
            "id": people[0].get("id"),
            "reveal_personal_emails": True
        }
        try:
            enrich_response = requests.post("https://api.apollo.io/v1/people/match", headers=headers, json=enrich_payload)
            if enrich_response.status_code == 200:
                enriched_person = enrich_response.json().get("person", {})
                if enriched_person:
                    people[0]["email"] = enriched_person.get("email")
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

def get_best_index(formatted_contacts):
    return 0

def add_contact_to_row(row, cols, get_emails=False):
    """Add contact information to a row using Apollo API and LLM analysis."""
    try:
        # Extract company name from the row
        company_website = row[cols["Website"]]
        if not isinstance(company_website, str):
            return row
            
        # Extract domain from website URL
        try:
            domain = company_website.replace("http://", "").replace("https://", "").replace("www.", "")
            domain = domain.split('/')[0]
        except:
            return row
            
        # Search for safety employee using Apollo API
        contacts = search_apollo(domain, get_emails)
        formatted_contacts = format_contacts_for_llm(contacts)
        print(formatted_contacts)
        best_index = get_best_index(formatted_contacts)

        # Update row with contact information
        if contacts and best_index < len(contacts):
            row[cols["First Name"]] = contacts[best_index].get("first_name")
            row[cols["Last Name"]] = contacts[best_index].get("last_name")
            row[cols["Title"]] = contacts[best_index].get("title")
            if get_emails:
                row[cols["Email"]] = contacts[best_index].get("email")
        
        return row
        
    except Exception as e:
        st.error(f"Error processing row: {e}")
        return row

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

            # Auto-detect column names
            columns = input_df.columns.str.lower()
            
            # Detect lead/organization name column
            lead_name_matches = columns.str.contains('organization|company|account|lead|name')
            lead_name_col = input_df.columns[lead_name_matches].tolist()[0] if any(lead_name_matches) else None
            
            # Detect website column
            website_matches = columns.str.contains('website|url|domain|web|site')
            website_col = input_df.columns[website_matches].tolist()[0] if any(website_matches) else None
            
            # Detect first name column
            first_name_matches = columns.str.contains('first.*name|fname|first')
            first_name_col = input_df.columns[first_name_matches].tolist()[0] if any(first_name_matches) else None
            
            # Detect last name column
            last_name_matches = columns.str.contains('last.*name|lname|last|surname')
            last_name_col = input_df.columns[last_name_matches].tolist()[0] if any(last_name_matches) else None
            
            # Detect title column
            title_matches = columns.str.contains('title|position|job')
            title_col = input_df.columns[title_matches].tolist()[0] if any(title_matches) else None
            
            # Detect email column
            email_matches = columns.str.contains('email|e-mail')
            email_col = input_df.columns[email_matches].tolist()[0] if any(email_matches) else None

            # Allow user to edit detected columns
            lead_name_column = st.text_input("Confirm/Edit organization names column", value=lead_name_col or "", key="lead_col")
            website_column = st.text_input("Confirm/Edit website column", value=website_col or "", key="website_col")
            name1_column = st.text_input("Confirm/Edit first names column", value=first_name_col or "", key="name1_col")
            name2_column = st.text_input("Confirm/Edit last names column", value=last_name_col or "", key="name2_col")
            title_column = st.text_input("Confirm/Edit titles column", value=title_col or "", key="title_col")
            email_column = st.text_input("Confirm/Edit emails column", value=email_col or "", key="email_col")

            # Validate columns
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

            # Add confirmation button and email checkbox before processing
            st.write("\n### Please confirm the column mappings above are correct before proceeding.")
            get_emails = st.checkbox("Get emails (Note: This will use additional API credits)", value=False)
            
            if not st.button("Confirm and Process File"):
                st.info("Click the button above when you're ready to process the file.")
                return
                
            # Rest of the processing code
            try:
                with st.status("Processing file...", expanded=True) as status:
                    st.write("Opening sheet...")
                    time.sleep(1)
                    st.write("Searching for employees...")
                    time.sleep(1)
                    st.write("Adding contact information...")
                    input_df.loc[input_df[name1_column].isna() & input_df[name2_column].isna() & input_df[title_column].isna() & input_df[email_column].isna()] = input_df.loc[input_df[name1_column].isna() & input_df[name2_column].isna() & input_df[title_column].isna() & input_df[email_column].isna()].apply(lambda x: add_contact_to_row(x, cols, get_emails), axis=1)
                    st.write("Contact search complete!")
                    
                    # Save to bytes buffer instead of file
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        input_df.to_excel(writer, index=False)
                    
                    # Offer file for download
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




    # def search_safety_employee(company_name):
#     """Search for a safety employee in a given company using the Apollo API."""
#     api_key = get_api_key()
#     base_url = "https://api.apollo.io/v1"
#     headers = {
#         "Content-Type": "application/json",
#         "Cache-Control": "no-cache"
#     }
#     company_name_trimmed = company_name[6:]
#     print(f"SEARCHING FOR {company_name_trimmed}")

#     payload = {
#         "api_key": api_key,
#         "q_organization_name": company_name_trimmed,
#         "page": 1,
#         "per_page": 10,
#         "person_titles": [
#             "safety", "security"
#         ],
#         "q_seniority_levels": ["Director", "Manager"]
#     }

#     row_dict = {
#         "First Name": None,
#         "Last Name": None,
#         "Title": None,
#         "Email": None
#     }

#     try:
#         response = requests.post(f"{base_url}/people/search", json=payload, headers=headers)
#         response.raise_for_status()
#         data = response.json()
#         people = data.get('people', [])
#         print(people)
#         if people:
#             # Use GPT to determine the most senior person
#             client = openai.OpenAI()
#             gpt_response = client.chat.completions.create(
#                 model="gpt-3.5-turbo",
#                 messages=[{
#                     "role": "system",
#                     "content": "You are a helpful assistant that analyzes job titles to determine seniority."
#                 }, {
#                     "role": "user",
#                     "content": f"""Given these job titles, return only the index number (0-9) of the most senior person that would be best to contact for selling Carbyne's call center safety software:
#                     {[person.get('title', '') for person in people]}
#                     Respond with only the number."""
#                 }],
#                 temperature=0
#             )
            
#             try:
#                 senior_index = int(gpt_response.choices[0].message.content.strip())
#                 person = people[senior_index]
#             except (ValueError, IndexError):
#                 # Fallback to first person if GPT fails
#                 person = people[0]
                
#             row_dict.update({
#                 "First Name": person.get("first_name"),
#                 "Last Name": person.get("last_name"),
#                 "Title": person.get("title")
#             })

#             enrich_payload = {
#                 "api_key": api_key,
#                 "id": person.get("id"),
#                 "reveal_personal_emails": True
#             }
#             print(enrich_payload)
#             enrich_response = requests.post(f"{base_url}/people/match", json=enrich_payload, headers=headers)
#             enrich_response.raise_for_status()
#             enrich_data = enrich_response.json().get("person", {})
#             row_dict["Email"] = enrich_data.get("email")

#     except requests.RequestException as e:
#         st.error(f"Request failed: {e}")

#     # Only display non-null values
#     non_null_data = {k: v for k, v in row_dict.items() if v is not None}
#     if non_null_data:
#         st.write(non_null_data)