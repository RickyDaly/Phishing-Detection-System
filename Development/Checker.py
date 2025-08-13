import dns.resolver

def check_spamhaus_dbl(domain):
    query_domain = f"{domain}.dbl.spamhaus.org"
    try:
        answers = dns.resolver.resolve(query_domain, 'A')
        result_ips = [answer.to_text() for answer in answers]
        return True, result_ips
    except dns.resolver.NXDOMAIN:
        return False, []
    except Exception as e:
        return False, str(e)

# Usage example
domain = "trustwallet-security.xyz"
listed, response = check_spamhaus_dbl(domain)
if listed:
    print(f"{domain} is listed! Response IPs: {response}")
else:
    print(f"{domain} is NOT listed.")